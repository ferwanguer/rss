""" Main function """
from models import load_newspapers_from_json

project: str = "rss-opinion"


def main(request):                                                          #pylint: disable=W0613
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    newspapers_list = load_newspapers_from_json('resources/newspapers.json')
    for newspaper in newspapers_list:
        newspaper.compare_feeds()

    return 'FUNCTION FINISHED', 200
