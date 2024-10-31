from django import forms

class ImageUploadForm(forms.Form):
    images = forms.ImageField(widget=forms.ClearableFileInput(attrs={'multiple': True}))
    quality = forms.IntegerField(initial=80, min_value=1, max_value=100)
    auto_enhance = forms.BooleanField(required=False)
    compression = forms.BooleanField(required=False)