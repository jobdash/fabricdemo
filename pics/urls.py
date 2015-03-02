from django.conf.urls import patterns, url

urlpatterns = patterns(
    'pics.views',
    # Examples:
    # url(r'^$', 'fabricdemo.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^hello/', 'hello', name='hello_world'),
    url(r'^cats/', 'cats', name='cats'),
    url(r'^recents/', 'recents', name='recents'),
)
