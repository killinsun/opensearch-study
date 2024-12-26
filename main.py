import os
from opensearchpy import OpenSearch

def get_opensearch_client():
    user = os.environ.get('OPENSEARCH_USER')
    password = os.environ.get('OPENSEARCH_PASSWORD', '')

    auth = (user, password)

    hosts = [
        {"host": "localhost", "port": 9200},
    ]
    client = OpenSearch(
        hosts=hosts,
        http_compress=True,
        http_auth=auth,
        use_ssl=True,
        verify_certs=False,
        ssl_show_warn=False,
    )

    return client

def check_client_is_alive(client):
    return client.ping()

def main():
    client = get_opensearch_client()
    is_alive = check_client_is_alive(client)
    print(f"Client is alive: {is_alive}")

if __name__ == "__main__":
    main()

