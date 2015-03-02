import json
import random

import arrow
from django.conf import settings
from django.shortcuts import render
import flickr_api
import requests


flickr_api.set_keys(
    api_key=settings.FLICKR_KEY,
    api_secret=settings.FLICKR_SECRET)

# Create your views here.
#
#


def hello(request):
    """
    Say hello!
    """
    return render(request, 'hello.html')


def oldcats(request):
    """
    Show pictures taged with cute or kittens on flickr
    """
    results = flickr_api.Photo.search(tags='cute,kittens', safe_search=1)
    return render(request, 'thumbs.html', {
        'PICS': [p.getPhotoFile(size_label='Thumbnail') for p in results]
    })


def cats(request):
    """
    Render the 100 most recently uploaded Flickr pictures
    """
    y = random.randrange(2000, 2016)
    m = random.randrange(1,13)
    d = random.randrange(1,28)

    ts = arrow.get(y, m, d).format('X')

    # get stuffz
    r = requests.get(
        'https://api.flickr.com/services/rest/',
        params={
            'api_key': settings.FLICKR_KEY,
            'method': 'flickr.photos.search',
            'format': 'json',
            'safe_search': 1,
            'max_taken_date': ts,
            'sort': 'interestingness-desc',
            'tags': 'kittens',
            'extras': 'url_t'
        })
    response = json.loads(r.text[14:-1])

    print response.get('photos', {}).get('photo', [])

    return render(request, 'thumbs.html', {
        'PICS': [
            x['url_t']
            for x in response.get('photos', {}).get('photo', [])
        ]
    })


def recents(request):
    """
    Render the 100 most recently uploaded Flickr pictures
    """
    # get stuffz
    r = requests.get(
        'https://api.flickr.com/services/rest/',
        params={
            'api_key': settings.FLICKR_KEY,
            'method': 'flickr.photos.getRecent',
            'format': 'json',
            'safe_search': 1,
            'extras': 'url_t'
        })
    response = json.loads(r.text[14:-1])

    # thumbnail url format string
    # pic_url = "https://farm{farm}.staticflickr.com/{server}/{id}_{secret}_t.jpg"

    return render(request, 'thumbs.html', {
        'PICS': [
            x['url_t']
            for x in response.get('photos', {}).get('photo', [])
        ]
    })
