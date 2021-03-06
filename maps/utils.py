import os

from django.template.loader import get_template
from django.template import Context
from django.http import HttpResponse

# filesystem path to the directory where icons are stored.
ICON_DIR = os.path.abspath(os.path.join(__file__, '..', 'static', 'icons'))

class RenderedRoute(object):
    name = ""
    kml = ""
    
    def __init__(self, name, kml):
        self.kml = kml
        self.name = name

class BaseFolder(object):
    index = 0
    name = ""
    
    def __iter__(self):
        return self
               
class RouteFolder(BaseFolder):
    
    rendered_routes = []
    
    style="#red_line"
    has_routes = True

    def __init__(self, name, qs, style=None):
        self.rendered_routes=[]
        self.name = name
        self.qs = qs
        if style:
            self.style = style
            
        self.figure_qs()
    
    def __unicode__(self):
        return "<RouteFolder: %s routes>" % len(self.rendered_routes)

    def figure_qs(self):
        for route in self.qs:
            self.rendered_routes.append(
                RenderedRoute(name=route['simple_rendered'],
                              kml=route['kml_rendered'],)
            )
    def next(self):
        try:
            ret = self.rendered_routes[self.index]
        except IndexError:
            raise StopIteration
            
        self.index+=1
        return ret
        
###############################################################################

class RenderedAirport(object):
    name = ""
    kml = ""
    identifier = ""
    ls = ""  #location summary: fancy name for the location, e.g.: "Newark, Ohio"; "Lolongwe, Malawi"
    
    def __init__(self, destination):
        self.kml = "%s,%s,0" % (destination.location.x, destination.location.y)
        self.name = destination.name
        self.ls = destination.location_summary()
        self.identifier = destination.identifier
        self.icon = destination.kml_icon()
    
class AirportFolder(BaseFolder):
    name = ""
    rendered_airports = []
    index = 0
    style="#red_line"
    has_points = True
    
    def __init__(self, name, qs, style=None):
        self.rendered_airports=[]
        self.name = name
        self.qs = qs
        if style:
            self.style = style
            
        self.figure_qs()

    def __unicode__(self):
        return "<AirportFolder: %s points>" % len(self.rendered_airports)

    def figure_qs(self):
        for airport in self.qs:
            if airport.location:
                ra=RenderedAirport(destination=airport)
                self.rendered_airports.append(ra)

    def next(self):
        try:
            ret = self.rendered_airports[self.index]
        except IndexError:
            raise StopIteration
            
        self.index+=1
        return ret

###############################################################################

def folders_to_kmz_response(folders, title=None,
                            add_icon=False, compression=True):
    
    import zipfile
    import cStringIO
    
    kml = get_template('base.kml').render(
        Context({"folders": folders})         
    )
    
    kml = kml.encode('utf-8')
    
    if not compression:
        return HttpResponse(kml, mimetype="text/plain")
    
    #################################
     
    sio = cStringIO.StringIO()
    
    z = zipfile.ZipFile(sio, 'w', compression=zipfile.ZIP_DEFLATED)
    z.writestr("doc.kml", kml)
    
    if add_icon:
        from django.conf import settings
        icon = "{0}/white_pad.png".format(ICON_DIR)
        z.write(icon, "files/icon_unknown.png")
        
        ############################################
        
        icon = "{0}/cyan_pad.png".format(ICON_DIR)
        z.write(icon, "files/cyan.png")

        icon = "{0}/gray_pad.png".format(ICON_DIR)
        z.write(icon, "files/gray.png")

        icon = "{0}/yellow_pad.png".format(ICON_DIR)
        z.write(icon, "files/yellow.png")

        icon = "{0}/red_pad.png".format(ICON_DIR)
        z.write(icon, "files/red.png")
        
        icon = "{0}/teal_pad.png".format(ICON_DIR)
        z.write(icon, "files/teal.png")

        icon = "{0}/white_pad.png".format(ICON_DIR)
        z.write(icon, "files/white.png")
        
        icon = "{0}/orange_pad.png".format(ICON_DIR)
        z.write(icon, "files/orange.png")

        icon = "{0}/green_pad.png".format(ICON_DIR)
        z.write(icon, "files/green.png")
        
        icon = "{0}/purple_pad.png".format(ICON_DIR)
        z.write(icon, "files/purple.png")
        
    z.close()
    
    return HttpResponse(sio.getvalue(),
                        mimetype="application/vnd.google-earth.kmz")

###############################################################################

def qs_to_time_kmz(qs, **kwargs):
    """
    From a routes queryset, return a folder'd up kmz file split up
    by type of flight time. pic, sic, dual received, etc
    """
    
    title = "Routes by type of flight time"
    
    dual_g = qs.filter(flight__dual_g__gt=0)\
               .values('kml_rendered', 'simple_rendered')\
               .order_by()\
               .distinct()
              
    dual_r = qs.filter(flight__dual_r__gt=0)\
               .values('kml_rendered', 'simple_rendered')\
               .order_by()\
               .distinct()
                          
    solo =   qs.filter(flight__solo__gt=0)\
               .values('kml_rendered', 'simple_rendered')\
               .order_by()\
               .distinct()
                          
    sic =    qs.filter(flight__sic__gt=0)\
               .values('kml_rendered', 'simple_rendered')\
               .order_by()\
               .distinct()
                          
    inst =   qs.filter(flight__act_inst__gt=0)\
               .values('kml_rendered', 'simple_rendered')\
               .order_by()\
               .distinct()
                          
    pic =    qs.filter(flight__pic__gt=0,
                       flight__dual_g=0,
                       flight__solo=0)\
               .values('kml_rendered', 'simple_rendered')\
               .order_by()\
               .distinct()

    folders = []
    if dual_g:
        folders.append(
            RouteFolder(name="Dual Given", qs=dual_g, style="#orange_line")
        )
        
    if solo:
        folders.append(
            RouteFolder(name="Solo", qs=solo, style="#red_line")
        )
        
    if pic:
        folders.append(
            RouteFolder(name="PIC", qs=pic, style="#red_line")
        )
        
    if dual_r:
        folders.append(
            RouteFolder(name="Dual Received", qs=dual_r, style="#blue_line")
        )

    if sic:
        folders.append(
            RouteFolder(name="SIC", qs=sic, style="#purple_line")
        )

    if inst:
        folders.append(
            RouteFolder(name="Actual Instrument", qs=inst, style="#green_line")
        )

    kwargs['add_icon'] = False
    
    if 'points' in kwargs.keys():
        k=kwargs.pop('points')
        title = k[0]
        points = k[1]
        kwargs['add_icon'] = True
        folders.append(
            AirportFolder(name=title, qs=points)
        )

    return folders_to_kmz_response(folders, title, **kwargs)



def qs_to_catclass_kmz(qs):
    """
    From a routes queryset, return a folder'd up kmz file split up
    by categoty class of the plane. single multi, helicopter, etc
    """
    
    title = "Routes by Multi/Single Engine"
        
    single = qs.filter(flight__plane__cat_class__in=[1,3])\
               .values('kml_rendered', 'simple_rendered')\
               .order_by()\
               .distinct()
                          
    multi = qs.filter(flight__plane__cat_class__in=[2,4])\
              .values('kml_rendered', 'simple_rendered')\
              .order_by()\
              .distinct()
                         
    other = qs.exclude(flight__plane__cat_class__lte=4)\
              .exclude(flight__plane__cat_class__gte=15)\
              .values('kml_rendered', 'simple_rendered')\
              .order_by()\
              .distinct()
    
    folders = []
    if single:
        folders.append(
            RouteFolder(name="Single-Engine", qs=single, style="#red_line")
        )
        
    if multi:
        folders.append(
            RouteFolder(name="Multi-Engine", qs=multi, style="#blue_line")
        )
    
    if other:
        folders.append(
            RouteFolder(name="Other", qs=other, style="#green_line")
        )
        
    return folders_to_kmz_response(folders, title)
