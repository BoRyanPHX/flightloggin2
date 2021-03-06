from django import forms

from constants import FILTER_FIELDS, FIELD_ABBV
    
def render_table(self):  #will be attached to the class in the function
    from main.table import html_table
    out=[]
    for field in FILTER_FIELDS:
        num_field = str(self[field])
        op = str(self[field + "_op"])
        title = getattr(self, 'fields')[field].label
        out.append( title + op + num_field )

    return html_table(out, 3)

def make_filter_kwargs(self, qs):
    """filter the queryset based on the form values, the name of this function
       should be renamed
    """
    
    if not self.is_valid():
        return qs
    
    def valid_filter(x):
        """
        Returns true if the field is a valid filterable field, that means it
        is neither an 'op' field, nor is the value None or a blank string
        """
        
        is_op = x[0].endswith("_op")
        is_none = x[1] is None
        is_blank = x[1] == ''
        
        return not (is_op or is_none or is_blank)
    
    fields = filter(valid_filter, self.cleaned_data.iteritems())
                    
    for field,val in fields:
        
        if field == "start_date":
            kwargs = {"date__gte": val}
            qs = qs.filter(**kwargs)
        
        elif field == "end_date":
            kwargs = {"date__lte": val}
            qs = qs.filter(**kwargs)
            
        elif field == 'person':
            kwargs = {"person__icontains": val}
            qs = qs.filter(**kwargs)
            
        elif field == 'remarks':
            kwargs = {"remarks__icontains": val}
            qs = qs.filter(**kwargs)
        
        elif "__" in field:       # all "__" filters
            kwargs = {"%s__icontains" % field: val}
            qs = qs.filter(**kwargs)
        
        elif val>=0:                     # all time filters

            # operator, '<', '>', or '='
            op = self.cleaned_data.get(field + "_op", "")
            
            if op == "0":
                qs = qs.filter_by_column(field, eq=val)
                
            elif op == "1":
                qs = qs.filter_by_column(field, gt=val)
                
            elif op == "2":
                qs = qs.filter_by_column(field, lt=val)

    return qs
    
    
def make_filter_form(user):
    from plane.models import Plane
    
    # all types the user has flown made into a list of strings
    types_qs = Plane.objects\
                 .filter(user=user)\
                 .values_list('type',flat=True)\
                 .order_by()\
                 .distinct()
    
    # make that list of types into a list of tuples that can be made into a
    # select box for the form
    types = [(t,t) for i,t in enumerate(types_qs)]
    types.insert(0, ("", "-------"))
    
    from plane.constants import CATEGORY_CLASSES
    CATEGORY_CLASSES = dict(CATEGORY_CLASSES)
    
    # same but now for cat classes
    cat_classes = Plane.objects\
                       .filter(user=user)\
                       .values_list('cat_class', flat=True)\
                       .order_by()\
                       .distinct()
                                            
    cc = [(t,CATEGORY_CLASSES[t]) for i,t in enumerate(cat_classes)]
    cc.insert(0, ("", "-------"))
    
    dp = {"class": "date_picker"}
    operators = ( (0, "="), (1, ">"), (2, "<") )
    
    fields = {
              'plane__tags':       forms.CharField(required=False),
              'plane__tailnumber': forms.CharField(required=False),
              
              'plane__type':       forms.ChoiceField(choices=types,
                                                     required=False),
                                                     
              'plane__cat_class':  forms.ChoiceField(choices=cc,
                                                     required=False),
                                                     
              'start_date':        forms.DateField(label="Start",
                                             required=False,
                                             widget=forms.TextInput(attrs=dp)),
                                             
              'end_date':          forms.DateField(label="End",
                                            required=False,
                                            widget=forms.TextInput(attrs=dp)),
                                            
              'person':            forms.CharField(required=False),
              'remarks':           forms.CharField(required=False),
              
              'route__fancy_rendered': forms.CharField(required=False,
                                                       label="Route"),
             }
             
    for field in FILTER_FIELDS:
        d = {
                field:          forms.FloatField(label=FIELD_ABBV[field],
                                             required=False,
                                             widget=forms.TextInput(
                                             attrs={"class": "small_picker"})
                                            ),
                                              
             "%s_op" % field:   forms.ChoiceField(choices=operators,
                                                  required=False,
                                                  widget=forms.Select(
                                                  attrs={"class": "op_select"})
                                                 ),
             }
             
        fields.update(d)
        
    FilterForm = type('FilterForm', (forms.BaseForm,), { 'base_fields': fields })
    FilterForm.render_table = render_table
    FilterForm.make_filter_kwargs = make_filter_kwargs
    
    return FilterForm











