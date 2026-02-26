from django import forms
from .models import FieldUpdate


class FieldUpdateForm(forms.ModelForm):
    class Meta:
        model = FieldUpdate
        fields = ['title', 'content', 'category', 'status', 'is_pinned']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-green-500 focus:ring-4 focus:ring-green-100',
                'placeholder': 'Enter update title...'
            }),
            'content': forms.Textarea(attrs={
                'class': 'w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-green-500 focus:ring-4 focus:ring-green-100',
                'rows': 4,
                'placeholder': 'Share your field update...'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-green-500 focus:ring-4 focus:ring-green-100'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-green-500 focus:ring-4 focus:ring-green-100'
            }),
            'is_pinned': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 rounded border-slate-300 text-green-700 focus:ring-green-500'
            })
        }



