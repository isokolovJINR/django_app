from django import forms


class CouponApplyFrom(forms.Form):
    code = forms.CharField()
