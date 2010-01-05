from django.test import TestCase
from models import Flight
from plane.models import Plane
from route.models import Route
from django.contrib.auth.models import User

class SimpleTest(TestCase):
    
    fixtures = ['airport/test-fixtures/test-location.json']
    
    def test_logbook_columns(self):
        """
        Tests that 1 + 1 always equals 2.
        """
        import datetime
        today = datetime.date.today()
        
        # multi engine land p2p > 50nm
        #########################################################
        
        p = Plane(tailnumber="N1234", cat_class=2, type='BE-55')
        p.save()
        
        r = Route.from_string('SNTR SSBT')
        
        f = Flight(plane=p, total=11.0, pic=10.0, date=today, route=r)
        f.save()
        
        self.failUnlessEqual(f.column('single'), "")
        self.failUnlessEqual(f.column('p2p'), "11.0")
        self.failUnlessEqual(f.column('m_pic'), "10.0")
        self.failUnlessEqual(f.column('plane'), "N1234 (BE-55)")
        self.failUnlessEqual(f.column('line_dist'), "959.7")
        self.failUnlessEqual(f.column('atp_xc'), "11.0")
                
        # multi-sea local
        #########################################################
        
        p = Plane(tailnumber="N5678", cat_class=4)
        p.save()
        
        r = Route.from_string('SNTR SNTR')
        
        f = Flight(plane=p, total=11.0, pic=10.0, date=today, route=r)
        f.save()
        
        self.failUnlessEqual(f.column('p2p'), "")
        self.failUnlessEqual(f.column('atp_xc'), "")
        self.failUnlessEqual(f.column('sea_pic'), "10.0")
        self.failUnlessEqual(f.column('tailnumber'), "N5678")
        
        # special remarks and events
        #########################################################
        
        p = Plane(tailnumber="N444444", cat_class=4, type="TYPE")
        p.save()
        
        r = Route.from_string('SNTR SNTR')
        
        f = Flight(plane=p,
                   total=11.0,
                   pic=10.0,
                   date=today,
                   route=r,
                   app=5,
                   holding=True,
                   tracking=True,
                   remarks="remarks derp",
                   ipc=True,
                   cfi_checkride=True)
        f.save()
        
        self.failUnlessEqual(f.column('type'), "TYPE")
        self.failUnlessEqual(f.column('app'), "5 HT")
        self.failUnlessEqual(f.column('sea_pic'), "10.0")
        self.failUnlessEqual(f.column('tailnumber'), "N444444")
        self.failUnlessEqual(f.column('remarks'), "<span class=\"flying_event\">[IPC][Instructor Checkride]</span> remarks derp")
        
    def test_empty_logbook_page(self):
        u = User(username='test')
        u.save()
        
        response = self.client.get('/test/logbook.html')
        self.failUnlessEqual(response.status_code, 200)
