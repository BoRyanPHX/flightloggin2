import re

from django import forms
from django.forms import ModelForm, ModelChoiceField
from django.contrib.admin import widgets
from django.forms.widgets import TextInput
from django.forms.util import ValidationError

from models import *
from route.forms import RouteField, RouteWidget
from plane.forms import PlaneField
from logbook.utils import from_minutes

class BlankHourWidget(TextInput):
    def _format_value_out(self, value):
        """In: decimal number
           Out: a string formatted to HH:MM
           a zero value outputs an empty string"""
        
        if value == 0:
            return ""

        return to_minutes(value)

    def render(self, name, value, attrs=None):
        value = self._format_value_out(value)
        attrs.update({"class": "float_line"})
        return super(BlankHourWidget, self).render(name, value, attrs)

    def _has_changed(self, initial, data):
        return super(BlankHourWidget, self)._has_changed(self._format_value_out(initial), data)
        
class BlankDecimalWidget(BlankHourWidget):
    def _format_value_out(self, value):
        """Prepare value for outout in the mass entry form
           In: decimal number
           Out: a string of that decimal number
           a zero value outputs an empty string"""
        
        if value == 0:
            return ""
        else:
            return "%.1f" % value
    
class BlankIntWidget(BlankHourWidget):
    def _format_value_out(self, value):
        """Prepare value for outout in the mass entry form
           In: an int
           Out: a string of that int
           a zero value outputs an empty string"""
        
        if value == 0:
            return ""
        else:
            return str(value)

########################################################################################

class BlankHourField(forms.Field):
    widget = BlankHourWidget
    def clean(self, value):
        super(BlankHourField, self).clean(value)
        
        if not value:
            return 0
        
        match = re.match("^([0-9]{1,3}):([0-9]{2})$", value)
        if match:
            print value
            dec = str(from_minutes(value))
            print dec
        else:
            dec = str(value)
            
        try:
            ev = eval(dec)
        except:
            raise ValidationError("Invalid Formatting")
            
        return ev
        
    def __init__(self, *args, **kwargs):
        super(BlankHourField, self).__init__(required=False, widget=None, label=None, initial=None,
                 help_text=None, error_messages=None, show_hidden_initial=False)
        
class BlankDecimalField(BlankHourField):
    widget = BlankDecimalWidget

class BlankIntField(BlankHourField):
    widget = BlankIntWidget
#####################################################################################################

class FlightForm(ModelForm):

    route =    RouteField(widget=forms.TextInput, required=False, queryset=Route.objects.get_empty_query_set())
    plane =    PlaneField(queryset=Plane.objects.get_empty_query_set(), required=True)
    
    total =    BlankDecimalField(label="Total Time")
    pic =      BlankDecimalField(label="PIC")
    sic =      BlankDecimalField(label="SIC")
    solo =     BlankDecimalField(label="Solo")
    dual_g =   BlankDecimalField(label="Dual Given")
    dual_r =   BlankDecimalField(label="Dual Received")
    xc =       BlankDecimalField(label="Cross Country")
    act_inst = BlankDecimalField(label="Actual Instrument")
    sim_inst = BlankDecimalField(label="Simulated Instrument")
    night =    BlankDecimalField(label="Night")
    
    day_l =    BlankIntField(label="Day Landings")
    night_l =  BlankIntField(label="Night Landings")
    app =      BlankIntField(label="Approaches")
    
    
    def __init__(self, *args, **kwargs):
        custom_queryset = False    
        if kwargs.has_key('planes_queryset'):
            custom_queryset = kwargs['planes_queryset']
            del kwargs['planes_queryset']
            
        super(FlightForm, self).__init__(*args, **kwargs)
        self.fields['date'].widget = widgets.AdminDateWidget()
        if custom_queryset:
            self.fields['plane'].queryset = custom_queryset

    class Meta:
        model = Flight
        exclude = ('user', )

#############################################################################################################

class FormsetFlightForm(FlightForm):
    remarks = forms.CharField(widget=forms.TextInput(attrs={"class": "remarks_line"}), required=False)
    person = forms.CharField(widget=forms.TextInput(attrs={"class": "person_line"}), required=False)
    route = RouteField(queryset=Route.objects.get_empty_query_set(), widget=RouteWidget)
    
    class Meta:
        model = Flight
        exclude = ('user', )

from django.forms.formsets import BaseFormSet
class FixedPlaneFormset(BaseFormSet):
    def __init__(self, *args, **kwargs): 
        if kwargs.has_key('planes_queryset'):
            self.custom_queryset = kwargs['planes_queryset']
            del kwargs['planes_queryset']         
        super(FixedPlaneFormset, self).__init__(*args, **kwargs)

    def add_fields(self, form, index):
        super(FixedPlaneFormset, self).add_fields(form, index)
        form.fields["plane"] = PlaneField(queryset=Plane.objects.get_empty_query_set(), required=True)
        form.fields['plane'].queryset = self.custom_queryset
        
        
from django.forms.models import BaseModelFormSet
class FixedPlaneModelFormset(BaseModelFormSet):
    def __init__(self, *args, **kwargs): 
        if kwargs.has_key('planes_queryset'):
            self.custom_queryset = kwargs['planes_queryset']
            del kwargs['planes_queryset']         
        super(FixedPlaneModelFormset, self).__init__(*args, **kwargs)

    def add_fields(self, form, index):
        super(FixedPlaneModelFormset, self).add_fields(form, index)
        form.fields["plane"] = PlaneField(queryset=Plane.objects.get_empty_query_set(), required=True)
        form.fields['plane'].queryset = self.custom_queryset


















