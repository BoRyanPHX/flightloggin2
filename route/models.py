import re

from django.contrib.gis.db import models
from django.db.models import Q

from share.middleware import share

from airport.models import Location

###############################################################################

class RouteBase(models.Model):
    
    route =    models.ForeignKey("Route")
    
    location =  models.ForeignKey(Location, null=True, blank=True)
    unknown =  models.CharField(max_length=30, blank=True, null=True)
    sequence = models.PositiveIntegerField()
    
    land = models.BooleanField()
    
    def __unicode__(self):
        
        loc_class = self.loc_class
        
        if loc_class == 0:
            ret = "unknown: %s" % self.unknown
        
        elif loc_class == 1:
            ret = "airport: %s" % self.location.identifier
        
        elif loc_class == 2:
            ret = "navaid: %s" % self.location.identifier
            
        elif loc_class == 3:
            ret = "custom: %s" % self.location.identifier
        
        if not self.land:
            ret = ret + " (NO LAND)"
            
        return ret
        
    def destination(self):
        return self.location or self.unknown
    
    @property
    def loc_class(self):
        """return the type of location, zero if it has no location"""
        
        return getattr(self.destination(), "loc_class", 0)
    
    def admin_loc_class(self):
        try:
            return getattr(self.destination(), "get_loc_class_display")() 
        except:
            return "Unknown"
    
    def owner(self):
        """Return the owner of the routebase. Only used in the admin"""
        try:
            return self.route.flight.all()[0].user.username
        except IndexError:
            return "??"
    
###############################################################################

class Route(models.Model):
    """Represents a route the user went on for the flight
    
    >>> r=Route.from_string("!custom -> @hyp  //vta -= mer")
    >>> r
    <Route: CUSTOM-HYP-KVTA-MER>
    >>> r.kml_rendered
    '-120.400001526,37.2193984985\n-82.4617996216,40.0247001648'
    >>> r.fancy_rendered
    u'<span title="Custom" class="found_custom">CUSTOM</span>-<span title="El Nido - VOR-DME" class="found_navaid">HYP</span>-<span title="Newark, Ohio" class="found_airport">KVTA</span>-<span title="MER" class="not_found">MER</span>'
    >>>
    >>> vta=Airport.objects.get(identifier="KVTA")
    >>> vta.municipality = "CHANGED NAME"
    >>> vta.save()
    >>>
    >>> r.easy_render()
    >>> r.fancy_rendered
    u'<span title="Custom" class="found_custom">CUSTOM</span>-<span title="El Nido - VOR-DME" class="found_navaid">HYP</span>-<span title="CHANGED NAME, Ohio" class="found_airport">KVTA</span>-<span title="MER" class="not_found">MER</span>'
    >>>
    >>> vta.delete()
    >>> vta.pk = 1000
    >>> vta.save()
    >>>
    >>> r.hard_render()
    >>> r.fancy_rendered
    u'<span title="Custom" class="found_custom">CUSTOM</span>-<span title="El Nido - VOR-DME" class="found_navaid">HYP</span>-<span title="CHANGED NAME, Ohio" class="found_airport">KVTA</span>-<span title="MER" class="not_found">MER</span>'
    >>>
    >>> vta = r.routebase_set.all()[2].location
    >>> vta
    <Location: KVTA>
    >>> vta.id
    1000
    """

    fancy_rendered =  models.TextField(blank=True, null=True)
    fallback_string = models.TextField(blank=True, null=True)
    simple_rendered = models.TextField(blank=True, null=True)
    kml_rendered =    models.TextField(blank=True, null=True)
    
    max_width_all = models.FloatField(null=True, default=0)
    max_width_land = models.FloatField(null=True, default=0)
    
    max_start_all = models.FloatField(null=True, default=0)
    max_start_land = models.FloatField(null=True, default=0)
    
    total_line_all = models.FloatField(null=True, default=0)
    total_line_land = models.FloatField(null=True, default=0)
    
    p2p = models.BooleanField()
    
    # a queryset of all landing points and all points, internal only
    land_points = None
    all_points = None
    
    def __unicode__(self):
        return self.simple_rendered or "err"
    
    def owner(self):
        """Return the owner of the route. Only used in the admin"""
        try:
            return self.flight.all()[0].user.username
        except IndexError:
            return "??"
    
    ##################################
    
    @classmethod
    def render_custom(cls, user):
        qs = cls.objects.filter(flight__user=user)\
                    .filter(routebase__location__loc_class=3)
        for r in qs:
            r.easy_render()
        return qs.count()
    
    @classmethod
    def easy_render_all(cls):
        """Re-renders ALL instances of Routes in the database. Easy render
           is not an expensive operation (relatively), so this isn't
           needing to be done in patches like hard_render.
        """
        qs = cls.objects.all()
        for r in qs:
            r.easy_render()
        return qs.count()
    
    @classmethod
    def hard_render_user(cls, username=None, user=None, no_dupe=True):
        """Hard re-render all routes for the given username
        """
        if username:
            from django.contrib.auth.models import User
            user=User.objects.get(username=username)
        
        kwargs = {'flight__user': user}
        
        if no_dupe:
            # only apply to routes that have zero routebases. Routes with no
            # routebases occur after all locations are deleted (which often
            # happens when the locations database is updated)
            kwargs.update({'routebase__isnull': True})
            
        from django.db.models import Max
        qs = cls.objects.filter(**kwargs)\
                        .distinct()\
                        .annotate(fid=Max('flight__id'))
        for r in qs:
            r.hard_render(user=user, flight_id=r.fid)
            
        return qs.count()
    
    @classmethod
    def hard_render_unknowns(cls):
        routes = cls.objects.filter(routebase__unknown__isnull=False)
        
        for r in routes:
            r.hard_render()
    
    @classmethod
    def from_string(cls, raw_route_string, user=None):
        """Create a route object from a waw string
        """
        # so we know which user to make the custom points from
        # if no user explicitly given, try to get the currently logged in user
        if not user:
            user = share.get_display_user()
            
        return MakeRoute(raw_route_string, user=user).get_route()
    
    #################################
    
    def render_distances(self):
        all_points = self._get_AllPoints()
        
        if not all_points or all_points.count() == 1:
            return ## nothing to measure, keep the defaults
        
        land_points = self._get_LandingPoints()
        
        self.max_start_all = self.calc_max_start(all_points)
        self.max_start_land = self.calc_max_start(land_points)
        
        self.max_width_all = self.calc_max_width(all_points)
        self.max_width_land = self.calc_max_width(land_points)
        
        self.total_line_all = self.calc_total_line(all_points)
        self.total_line_land = self.calc_total_line(land_points)
        
    #################################
    
    def _get_LandingPoints(self):
        """return a queryset containing all points where a landing took
           place.
        """
        
        if not self.land_points:
            self.land_points = Location.objects.filter(
                    location__isnull=False,    # has valid coordinates
                    routebase__route=self,     # is connected to this route
                    routebase__land=True,      # depicts a landing
            ).distinct()
            
        return self.land_points
    
    def _get_AllPoints(self):
        """return a queryset of all points, regardless whether a landing
           was done there or not
        """
        
        if not self.all_points:
            self.all_points = Location.objects.filter(
                    location__isnull=False,
                    routebase__route=self,
            ).distinct()
            
            #self.line_kml = self.all_points.make_line().kml
            
        return self.all_points
    
    def calc_max_width(self, a=None):
        """returns the max distance between any two points in the
           route.a
        """
        
        if not a:
            a = self._get_AllPoints()
        
        mp = a.collect()
        ct = mp.envelope.centroid
        
        dist = []
        from utils import coord_dist
        for i,po in enumerate(mp): 
            dist.append(coord_dist(po, ct))
        
        #since we're measuring from the center, multiply by 2    
        diameter = max(dist) * 2
        
        return diameter
    
    ################################
    
    def calc_max_start(self, a=None):
        """Returns the max distance between any point in the route and the
           starting point. Used for ATP XC distance.
           
           >>> r=Route.from_string('kvta kuni')
           >>> r.start_distance()
           50.003471947098973
           >>> r=Route.from_string('kmer kvta')
           >>> r.start_distance()
           0.0
           >>> r=Route.from_string('kvta')
           >>> r.start_distance()
           0.0
           
        """
        
        if not a:
            a = self._get_AllPoints()
        
        mp = a.collect()
        start = a[0].location
        
        dist = []
        from utils import coord_dist
        for i,po in enumerate(mp):
            dist.append(coord_dist(po, start))
         
        return max(dist)
    
    def calc_total_line(self, a=None):
        """returns the distance between each point in the route"""
        if not a:
            a = self._get_AllPoints()
            
        ls = a.make_line()
        
        dist = []
        from utils import coord_dist
        for i,po in enumerate(ls):
            try:
                next = ls[1+i]
            except:
                pass
            else:
                from django.contrib.gis.geos import Point
                dist.append(coord_dist(Point(po), Point(next)))
         
        return sum(dist)
    ################################
    
    def easy_render(self):
        """Rerenders the HTML for displaying the route. Takes info from the
           already defines routebases. For rerendering after updating Airport
           info, use hard_render()
        """
        fancy = []
        simple = []
        kml = []
        
        for rb in self.routebase_set.all().order_by('sequence'):
            
            dest = rb.destination()
            loc_class = rb.loc_class
            
            if loc_class == 1:
                class_ = "found_airport"
            elif loc_class == 2:
                class_ = "found_navaid"
            elif loc_class == 3:
                class_ = "found_custom"
            elif loc_class == 0:
                class_ = "not_found"
                
            # only write a kml if coordinates are known
            if getattr(dest, "location", None):
                kml.append("%s,%s" % (dest.location.x, dest.location.y), )
                
            if loc_class > 0:   
                fancy.append("<span title=\"%s\" class=\"%s\">%s</span>" %
                            (dest.title_display(), class_, dest.identifier ), )
                simple.append(rb.destination().identifier)
            elif loc_class == 0:
                fancy.append("<span title=\"%s\" class=\"%s\">%s</span>" %
                            (dest, class_, dest ), )
                simple.append(rb.destination())
            
        self.kml_rendered = "\n".join(kml)
        self.fancy_rendered = "-".join(fancy)
        self.simple_rendered = "-".join(simple)
        
        self.render_distances()
        
        self.save()
        
    def hard_render(self, user=None, username=None, flight_id=None):
        """Spawns a new Route object based on it's own fallback_string,
           connects it to the flight that the old route was connected to.
           Then returns the newly created Route instance. This is used to
           redo all the routebases after the navaid/airport database has been
           updated and all the primary keys are changed.
        """
        
        if not flight_id:
            try:
                f = self.flight.all()[0]
                
            except IndexError:  
                # no flight associated with this route
                pass
            
            else:
                flight_id = f.id
                user = f.user
                print "got userid from flight join"
            
        if (not user) and username:
            from django.contrib.auth.models import User
            user = User.objects.get(username=username)
            print "got user from seperate query"
            
        if not user and not username:
            user = share.get_display_user()
            print "got user from share thingy"
        
        new_route = MakeRoute(self.fallback_string, user).get_route()
        
        if flight_id:
            from logbook.models import Flight
            flight = Flight.objects.get(pk=flight_id)
            flight.route = new_route
            flight.save()
        
        return new_route
    
###############################################################################
  
class MakeRoute(object):
    """creates a route object from a string. The constructor takes a user
       instance because it needs to know which "namespace" to use for
       looking up custom places.
    """
    
    def __init__(self, fallback_string, user):
        self.user=user
       
        if not fallback_string:
            self.route = None
            return None
        
        route = Route(fallback_string=fallback_string, p2p=False)
        route.save()
        
        is_p2p, routebases = self.make_routebases_from_fallback_string(route)
        
        route.p2p = is_p2p
        
        for routebase in routebases:
            routebase.route = route
            routebase.save()
            
        route.easy_render()
        
        self.route = route
    
    def get_route(self):
        return self.route
    
    ###########################################################
    ###########################################################
   
            
    def normalize(self, string):
        """removes all cruf away from the route string, returns only the
           alpha numeric characters with clean seperators
        """
        
        import re
        string = string.upper()
        string = string.replace("LOCAL", " ")
        string = string.replace(" TO ", " ")
        return re.sub(r'[^A-Z0-9!@]+', ' ', string).strip()

    ###########################################################
    ########################################################### 
        
    def find_navaid(self, ident, i, last_rb=None):
        """Searches the database for the navaid object according to ident.
           if it finds a match,returns the routebase object
        """
               
        if last_rb:
            navaid = Location.objects.filter(loc_class=2, identifier=ident)
            #if more than 1 navaids come up,
            if navaid.count() > 1:
                #run another query to find the nearest
                last_point = last_rb.location 
                navaid = navaid.distance(last_point.location).order_by('distance')[0]  
            elif navaid.count() == 0:
                navaid = None
            else:
                navaid = navaid[0]
        else:
            # no previous routebases,
            # dont other with the extra queries trying to find the nearest 
            # based on the last
            navaid = Location.goon(loc_class=2,
                                   identifier=ident)
        if navaid:
            return RouteBase(location=navaid, sequence=i)
        
        return None
        
    ###############################################################################

    def find_custom(self, ident, i, force=False):
        """Tries to find the custom point, if it can't find one, and
           force = True, it adds it to the user's custom list.
        """
        
        ident = ident[:8]
        
        if force:
            cu,cr = Location.objects.get_or_create(user=self.user,
                                                  loc_class=3,
                                                  identifier=ident)
        else:
            cu = Location.goon(loc_class=3,
                               user=self.user,
                               identifier=ident)

        if cu:
            return RouteBase(location=cu, sequence=i)
        else:
            return None

    ###########################################################################

    def find_airport(self, ident, i, p2p):
        airport = Location.goon(loc_class=1, identifier=ident)
            
        if not airport and len(ident) == 3:
            # if the ident is 3 letters and no hit, try again with an added 'K'
            airport = Location.goon(loc_class=1,
                                    identifier="K%s" % ident)

        if airport:
            # a landing airport, eligable for p2p testing
            p2p.append(airport.pk)          
            return RouteBase(location=airport, sequence=i)
        
        return None

    def make_routebases_from_fallback_string(self, route):
        """returns a list of RouteBase objects according to the fallback_string,
        basically hard_render()
        """
        
        fbs = self.normalize(route.fallback_string)
        points = fbs.split()                        # MER-VGA -> ['MER', 'VGA']
        unknown = False
        p2p = []
        routebases = []
        
        for i, ident in enumerate(points):
        
            if "@" in ident:        # "@" means we didn't land
                land = False
            else:
                land = True
                
            if "!" in ident:        # "!" means it's a custom place
                custom = True
            else:
                custom = False
                
            #replace all the control characters now that we know their purpose
            ident = ident.replace('!','').replace('@','')
                
            if not land and not custom:     # must be a navaid
                # is this the first routebase? if so don't try to guess which
                # navaid is closest to the previous point
                
                first_rb = len(routebases) == 0  
                if not first_rb and not routebases[i-1].unknown:
                    routebase = self.find_navaid(ident, i, last_rb=routebases[i-1])
                else:
                    routebase = self.find_navaid(ident, i)
            
            elif custom:
                # force=True means if it can't find the 'custom', then make it
                routebase = self.find_custom(ident, i, force=True)
                
            else:                  #must be an airport  
                routebase = self.find_airport(ident, i, p2p=p2p)
                if not routebase:
                    # if the airport can't be found, see if theres a 'custom'
                    # bythe same identifier
                    routebase = self.find_custom(ident, i, force=False)
                
            #######################################################################
           
            # no routebase? must be unknown
            if not routebase:
                routebase = RouteBase(unknown=ident, sequence=i)
                
                # not a unidentified navaid, assume a landing
                if land:
                    p2p.append(ident)
            
            routebase.land = land
            routebases.append(routebase)

        return len(set(p2p)) > 1, routebases
