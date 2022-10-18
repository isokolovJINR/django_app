from django.contrib.sitemaps import Sitemap
from .models import Post


class PostSitemap(Sitemap):
    changerfreq = 'weekly'
    priority = 0.9

    def items(self):
        return Post.published.all()

    def get_latest_lastmod(self, obj):
        return obj.updated
