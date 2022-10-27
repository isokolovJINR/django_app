from django.utils.text import slugify


def create_slug(image):
    slug = ''
    if not image.slug:
        slug = slugify(image.title)
    return slug

