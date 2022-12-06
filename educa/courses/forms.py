from django import forms
from django.forms.models import inlineformset_factory
from .models import Course, Module, Folder

ModuleFormSet = inlineformset_factory(Course, Module,
                                      fields=['title',
                                              'description'],
                                      extra=2,
                                      can_delete=True)


class FolderCreateForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ('name',)

    # def clean_url(self):
    #     url = self.cleaned_data['url']
    #
    #     valid_extensions = ['jpg', 'jpeg']
    #     extension = url.rsplit('.', 1)[1].lower()
    #     if extension not in valid_extensions:
    #         raise forms.ValidationError('The given URL does not '
    #                                     'match valid image extensions.')
    #     return url

    # def save(self, force_insert=False,
    #          force_update=False,
    #          commit=True):
    #
    #     folder = super().save(commit=False)
    #
    #
    #     folder.image.save(image_name,
    #                      ContentFile(response.read()),
    #                      save=False)
    #     if commit:
    #         image.save()
    #     return image