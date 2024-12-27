import os
from opensearchpy import OpenSearch, helpers
from datasets import load_dataset
from pydantic import BaseModel
import click

from dotenv import load_dotenv

load_dotenv()


class Review(BaseModel):
    id: str
    text: str


opensearch_schema = {
    "settings": {
        "number_of_shards": 1,
        "analysis": {
            "filter": {
                "kuromoji_baseform_filter": {"type": "kuromoji_baseform"},
                "cjk_width_filter": {"type": "cjk_width"},
                "ja_stop_filter": {"type": "stop", "stopwords": "_japanese_"},
                "kuromoji_stemmer_filter": {"type": "kuromoji_stemmer"},
                "lowercase_filter": {"type": "lowercase"},
            },
            "analyzer": {
                "kuromoji_analyzer": {
                    "type": "custom",
                    "tokenizer": "kuromoji_tokenizer",
                    "filter": [
                        "kuromoji_baseform_filter",
                        "cjk_width_filter",
                        "ja_stop_filter",
                        "kuromoji_stemmer_filter",
                        "lowercase_filter",
                    ],
                }
            },
        },
    },
    "mappings": {
        "properties": {
            "id": {
                "type": "keyword"
            },
            "text": {
                "type": "text",
                "analyzer": "kuromoji_analyzer"
            }
        }
    }
}


def get_opensearch_client():
    user = os.environ.get('OPENSEARCH_USER')
    password = os.environ.get('OPENSEARCH_PASSWORD', '')
    auth = (user, password)

    hosts = [{"host": "localhost", "port": 9200}]
    client = OpenSearch(
        hosts=hosts,
        http_compress=True,
        http_auth=auth,
        use_ssl=True,
        verify_certs=False,
        ssl_show_warn=False,
    )
    return client


def create_index(client, index_name):
    if client.indices.exists(index=index_name):
        return
    return client.indices.create(index=index_name, body=opensearch_schema)


def bulk_index_reviews(client, index_name, reviews: list[Review]):
    docs = []
    for review in reviews:
        doc = {
            "_index": index_name,
            "_id": review.id,
            "_source": {
                "id": review.id,
                "text": review.text
            }
        }
        docs.append(doc)

    helpers.bulk(client, docs)


def get_reviews_from_dataset() -> list[Review]:
    dataset = load_dataset('mteb/amazon_reviews_multi', 'ja', split='train')
    reviews = []
    for review in dataset:
        reviews.append(Review(id=review['id'], text=review['text']))
    return reviews


def search_reviews(client, index_name: str, query_text: str, size: int = 5):
    query = {
        "query": {
            "match": {
                "text": {
                    "query": query_text,
                    "analyzer": "kuromoji_analyzer"
                    # "analyzer": "standard"
                }
            }
        }
    }

    response = client.search(
        body=query,
        index=index_name,
        size=size
    )

    return response['hits']['hits']


@click.group()
def cli():
    """OpenSearch CLI tool for managing and searching Amazon reviews"""
    pass


@cli.command()
@click.option('--index-name', '-n', default='amazon_reviews', help='Name of the index')
def init(index_name):
    """Initialize and populate the index with Amazon reviews"""
    try:
        client = get_opensearch_client()
        create_index(client, index_name)

        reviews = get_reviews_from_dataset()
        click.echo(f"Indexing {len(reviews)} reviews...")
        bulk_index_reviews(client, index_name, reviews=reviews)
        click.echo("✨ Finished indexing successfully!")
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)


@cli.command()
@click.argument('index_name')
@click.argument('query_text')
@click.option('--size', '-n', default=5, help='Number of results to return')
def search(index_name, query_text, size):
    """Search for reviews in the specified index"""
    try:
        client = get_opensearch_client()
        results = search_reviews(client, index_name, query_text, size)

        if not results:
            click.echo("No results found.")
            return

        click.echo(f"\nFound {len(results)} results:\n")
        for hit in results:
            score = hit['_score']
            text = hit['_source']['text']
            click.echo(f"Score: {score:.2f}")
            click.echo(f"Text: {text}")
            click.echo("-" * 80)
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        stack_trace = click.get_current_context().obj.get('show_stacktrace', False)
        click.echo("stack_trace")
        if stack_trace:
            raise e


if __name__ == '__main__':
    cli()
