from django.db import models, transaction
from core.models import Service, PlCoreBase, Slice, Instance, Tenant, TenantWithContainer, Node, Image, User, Flavor, NetworkParameter, NetworkParameterType, Port, AddressPool
from core.models.plcorebase import StrippedCharField
import os
from django.forms.models import model_to_dict
from django.db.models import *
from operator import itemgetter, attrgetter, methodcaller
from core.models import Tag
from core.models.service import LeastLoadedNodeScheduler
import traceback
from xos.exceptions import *
from xos.config import Config

from models_decl import VEPCService_decl, VEPCTenant_decl
from services.vhss.models import VHSSService, VHSSTenant
from services.vmme.models import VMMEService, VMMETenant
from services.vmm.models import VMMService, VMMTenant
from services.vsm.models import VSMService, VSMTenant
from services.vsgwc.models import VSGWCService, VSGWCTenant
from services.vsgwu.models import VSGWUService, VSGWUTenant
from services.vpgwc.models import VPGWCService, VPGWCTenant
from services.vpgwu.models import VPGWUService, VPGWUTenant

class VEPCService(VEPCService_decl):
   class Meta:
        proxy = True
        
class VEPCTenant(VEPCTenant_decl):
   class Meta:
        proxy = True

   def __init__(self, *args, **kwargs):
       vepcservices = VEPCService.get_service_objects().all()
       if vepcservices:
           self._meta.get_field("provider_service").default = vepcservices[0].id
       super(VEPCTenant, self).__init__(*args, **kwargs)
       self.cached_vhss = None
       self.cached_vmme = None
       self.cached_vmm = None
       self.cached_vsm = None
       self.cached_vsgwc = None
       self.cached_vsgwu = None
       self.cached_vpgwc = None
       self.cached_vpgwu = None
   
   @property
   def vhss(self):
       vhss = self.get_newest_subscribed_tenant(VHSSTenant)
       if not vhss:
           return None

       if (self.cached_vhss) and (self.cached_vhss.id == vhss.id):
           return self.cached_vhss

       vhss.caller = self.creator
       self.cached_vhss = vhss
       return vhss

   @vhss.setter
   def vhss(self, value):
       raise XOSConfigurationError("VEPCTenant.vhss setter is not implemented")

   def get_vhss_service(self):
       vhssservices = VHSSService.get_service_objects().all()
       if not vhssservices:
           raise XOSConfigurationError("No VHSS Services available")
       return vhssservices[0]

   def manage_vhss(self):
       # Each vEPC object owns exactly one VHSSTenant object
       if self.deleted:
           return

       if self.has_vhss:
           if self.vhss is None:
               vhss = self.get_vhss_service().create_tenant(subscriber_tenant=self, creator=self.creator)
               #vhss = self.get_vhss_service().create_tenant(subscriber_tenant=self, creator=self.creator, vhss_vendor=self.vhss_vendor)
       else:
           if self.vhss:
               self.cleanup_vhss()

   def cleanup_vhss(self):
       if self.vhss:
           self.vhss.delete()

   @property
   def vmme(self):
       vmme = self.get_newest_subscribed_tenant(VMMETenant)
       if not vmme:
           return None

       if (self.cached_vmme) and (self.cached_vmme.id == vmme.id):
           return self.cached_vmme

       vmme.caller = self.creator
       self.cached_vmme = vmme
       return vmme

   @vmme.setter
   def vmme(self, value):
       raise XOSConfigurationError("VEPCTenant.vmme setter is not implemented")

   def get_vmme_service(self):
       vmmeservices = VMMEService.get_service_objects().all()
       if not vmmeservices:
           raise XOSConfigurationError("No VMME Services available")
       return vmmeservices[0]

   def manage_vmme(self):
       # Each vEPC object owns exactly one VMMETenant object
       if self.deleted:
           return

       if self.has_vmme:
           if self.vmme is None:
               vmme = self.get_vmme_service().create_tenant(subscriber_tenant=self, creator=self.creator)
	       #vmme = self.get_vmme_service().create_tenant(subscriber_tenant=self, creator=self.creator, vmme_vendor=self.vmme_vendor)
       else:
           if self.vmme:
               self.cleanup_vmme()

   def cleanup_vmme(self):
       if self.vmme:
           self.vmme.delete()

   @property
   def vmm(self):
       vmm = self.get_newest_subscribed_tenant(VMMTenant)
       if not vmm:
           return None

       if (self.cached_vmm) and (self.cached_vmm.id == vmm.id):
           return self.cached_vmm

       vmm.caller = self.creator
       self.cached_vmm = vmm
       return vmm

   @vmm.setter
   def vmm(self, value):
       raise XOSConfigurationError("VEPCTenant.vmm setter is not implemented")

   def get_vmm_service(self):
       vmmservices = VMMService.get_service_objects().all()
       if not vmmservices:
           raise XOSConfigurationError("No VMM Services available")
       return vmmservices[0]

   def manage_vmm(self):
       # Each vEPC object owns exactly one VMMTenant object
       if self.deleted:
           return

       if self.has_vmm:
           if self.vmm is None:
               vmm = self.get_vmm_service().create_tenant(subscriber_tenant=self, creator=self.creator)
	       #vmm = self.get_vmm_service().create_tenant(subscriber_tenant=self, creator=self.creator, vmm_vendor=self.vmm_vendor)
       else:
           if self.vmm:
               self.cleanup_vmm()

   def cleanup_vmm(self):
       if self.vmm:
           self.vmm.delete()

   @property
   def vsm(self):
       vsm = self.get_newest_subscribed_tenant(VSMTenant)
       if not vsm:
           return None

       if (self.cached_vsm) and (self.cached_vsm.id == vsm.id):
           return self.cached_vsm

       vsm.caller = self.creator
       self.cached_vsm = vsm
       return vsm

   @vsm.setter
   def vsm(self, value):
       raise XOSConfigurationError("VEPCTenant.vsm setter is not implemented")

   def get_vsm_service(self):
       vsmservices = VSMService.get_service_objects().all()
       if not vsmservices:
           raise XOSConfigurationError("No VSM Services available")
       return vsmservices[0]

   def manage_vsm(self):
       # Each vEPC object owns exactly one VSMTenant object
       if self.deleted:
           return

       if self.has_vsm:
           if self.vsm is None:
               vsm = self.get_vsm_service().create_tenant(subscriber_tenant=self, creator=self.creator)
	       #vsm = self.get_vsm_service().create_tenant(subscriber_tenant=self, creator=self.creator, vsm_vendor=self.vsm_vendor)
       else:
           if self.vsm:
               self.cleanup_vsm()

   def cleanup_vsm(self):
       if self.vsm:
           self.vsm.delete()

   @property
   def vsgwc(self):
       vsgwc = self.get_newest_subscribed_tenant(VSGWCTenant)
       if not vsgwc:
           return None

       if (self.cached_vsgwc) and (self.cached_vsgwc.id == vsgwc.id):
           return self.cached_vsgwc

       vsgwc.caller = self.creator
       self.cached_vsgwc = vsgwc
       return vsgwc

   @vsgwc.setter
   def vsgwc(self, value):
       raise XOSConfigurationError("VEPCTenant.vsgwc setter is not implemented")

   def get_vsgwc_service(self):
       vsgwcservices = VSGWCService.get_service_objects().all()
       if not vsgwcservices:
           raise XOSConfigurationError("No VSGWC Services available")
       return vsgwcservices[0]

   def manage_vsgwc(self):
       # Each vEPC object owns exactly one VSGWCTenant object
       if self.deleted:
           return

       if self.has_vsgwc:
           if self.vsgwc is None:
               vsgwc = self.get_vsgwc_service().create_tenant(subscriber_tenant=self, creator=self.creator)
	       #vsgwc = self.get_vsgwc_service().create_tenant(subscriber_tenant=self, creator=self.creator, vsgwc_vendor=self.vsgwc_vendor)
       else:
           if self.vsgwc:
               self.cleanup_vsgwc()

   def cleanup_vsgwc(self):
       if self.vsgwc:
           self.vsgwc.delete()

   @property
   def vsgwu(self):
       vsgwu = self.get_newest_subscribed_tenant(VSGWUTenant)
       if not vsgwu:
           return None

       if (self.cached_vsgwu) and (self.cached_vsgwu.id == vsgwu.id):
           return self.cached_vsgwu

       vsgwu.caller = self.creator
       self.cached_vsgwu = vsgwu
       return vsgwu

   @vsgwu.setter
   def vsgwu(self, value):
       raise XOSConfigurationError("VEPCTenant.vsgwu setter is not implemented")

   def get_vsgwu_service(self):
       vsgwuservices = VSGWUService.get_service_objects().all()
       if not vsgwuservices:
           raise XOSConfigurationError("No VSGWU Services available")
       return vsgwuservices[0]

   def manage_vsgwu(self):
       # Each vEPC object owns exactly one VSGWUTenant object
       if self.deleted:
           return

       if self.has_vsgwu:
           if self.vsgwu is None:
               vsgwu = self.get_vsgwu_service().create_tenant(subscriber_tenant=self, creator=self.creator)
	       #vsgwu = self.get_vsgwu_service().create_tenant(subscriber_tenant=self, creator=self.creator, vsgwu_vendor=self.vsgwu_vendor)
       else:
           if self.vsgwu:
               self.cleanup_vsgwu()

   def cleanup_vsgwu(self):
       if self.vsgwu:
           self.vsgwu.delete()

   @property
   def vpgwc(self):
       vpgwc = self.get_newest_subscribed_tenant(VPGWCTenant)
       if not vpgwc:
           return None

       if (self.cached_vpgwc) and (self.cached_vpgwc.id == vpgwc.id):
           return self.cached_vpgwc

       vpgwc.caller = self.creator
       self.cached_vpgwc = vpgwc
       return vpgwc

   @vpgwc.setter
   def vpgwc(self, value):
       raise XOSConfigurationError("VEPCTenant.vpgwc setter is not implemented")

   def get_vpgwc_service(self):
       vpgwcservices = VPGWCService.get_service_objects().all()
       if not vpgwcservices:
           raise XOSConfigurationError("No VPGWC Services available")
       return vpgwcservices[0]

   def manage_vpgwc(self):
       # Each vEPC object owns exactly one VPGWCTenant object
       if self.deleted:
           return

       if self.has_vpgwc:
           if self.vpgwc is None:
               vpgwc = self.get_vpgwc_service().create_tenant(subscriber_tenant=self, creator=self.creator)
	       #vpgwc = self.get_vpgwc_service().create_tenant(subscriber_tenant=self, creator=self.creator, vpgwc_vendor=self.vpgwc_vendor)
       else:
           if self.vpgwc:
               self.cleanup_vpgwc()

   def cleanup_vpgwc(self):
       if self.vpgwc:
           self.vpgwc.delete()

   @property
   def vpgwu(self):
       vpgwu = self.get_newest_subscribed_tenant(VPGWUTenant)
       if not vpgwu:
           return None

       if (self.cached_vpgwu) and (self.cached_vpgwu.id == vpgwu.id):
           return self.cached_vpgwu

       vpgwu.caller = self.creator
       self.cached_vpgwu = vpgwu
       return vpgwu

   @vpgwu.setter
   def vpgwu(self, value):
       raise XOSConfigurationError("VEPCTenant.vpgwu setter is not implemented")

   def get_vpgwu_service(self):
       vpgwuservices = VPGWUService.get_service_objects().all()
       if not vpgwuservices:
           raise XOSConfigurationError("No VPGWU Services available")
       return vpgwuservices[0]

   def manage_vpgwu(self):
       # Each vEPC object owns exactly one VPGWUTenant object
       if self.deleted:
           return

       if self.has_vpgwu:
           if self.vpgwu is None:
               vpgwu = self.get_vpgwu_service().create_tenant(subscriber_tenant=self, creator=self.creator)
	       #vpgwu = self.get_vpgwu_service().create_tenant(subscriber_tenant=self, creator=self.creator, vpgwu_vendor=self.vpgwu_vendor)
       else:
           if self.vpgwu:
               self.cleanup_vpgwu()

   def cleanup_vpgwu(self):
       if self.vpgwu:
           self.vpgwu.delete()

   def cleanup_orphans(self):
       # ensure vMME only has at most one of each service
       cur_vhss = self.vhss
       cur_vmme = self.vmme
       cur_vmm = self.vmm
       cur_vsm = self.vsm
       cur_vsgwc = self.vsgwc
       cur_vsgwu = self.vsgwu
       cur_vpgwc = self.vpgwc
       cur_vpgwu = self.vpgwu
          
       for vhss in list(self.get_subscribed_tenants(VHSSTenant)):
           if (not cur_vhss) or (vhss.id != cur_vhss.id):
               vhss.delete()
   
       for vmme in list(self.get_subscribed_tenants(VMMETenant)):
           if (not cur_vmme) or (vmme.id != cur_vmme.id):
               vmme.delete()
   
       for vmm in list(self.get_subscribed_tenants(VMMTenant)):
           if (not cur_vmm) or (vmm.id != cur_vmm.id):
               vmm.delete()
   
       for vsm in list(self.get_subscribed_tenants(VSMTenant)):
           if (not cur_vsm) or (vsm.id != cur_vsm.id):
               vsm.delete()
   
       for vsgwc in list(self.get_subscribed_tenants(VSGWCTenant)):
           if (not cur_vsgwc) or (vsgwc.id != cur_vsgwc.id):
               vsgwc.delete()
   
       for vsgwu in list(self.get_subscribed_tenants(VSGWUTenant)):
           if (not cur_vsgwu) or (vsgwu.id != cur_vsgwu.id):
               vsgwu.delete()
   
       for vpgwc in list(self.get_subscribed_tenants(VPGWCTenant)):
           if (not cur_vpgwc) or (vpgwc.id != cur_vpgwc.id):
               vpgwc.delete()
   
       for vpgwu in list(self.get_subscribed_tenants(VPGWUTenant)):
           if (not cur_vpgwu) or (vpgwu.id != cur_vpgwu.id):
               vpgwu.delete()
   
   def save(self, *args, **kwargs):
       #https://stackoverflow.com/questions/31831620/can-i-make-at-least-one-field-a-requirement-on-a-django-model
       if not (self.has_vhss or self.has_vmme or self.has_vmm or self.has_vsm or self.has_vsgwc or self.has_vsgwu or self.has_vpgwc or self.has_vpgwu):
           raise XOSConfigurationError("Cannot have an empty service chain")
   
       super(VEPCTenant, self).save(*args, **kwargs)
       # This call needs to happen so that an instance is created for this
       # tenant is created in the slice. One instance is created per tenant.
       model_policy_vepctenant(self.pk)

   def delete(self, *args, **kwargs):
       # Delete the dependent instances on this service chain tenant
       self.cleanup_vhss()
       self.cleanup_vmme()
       self.cleanup_vmm()
       self.cleanup_vsm()
       self.cleanup_vsgwc()
       self.cleanup_vsgwu()
       self.cleanup_vpgwc()
       self.cleanup_vpgwu()
       super(VEPCTenant, self).delete(*args, **kwargs)
   
def model_policy_vepctenant(pk):
    # TODO: this should be made in to a real model_policy
    with transaction.atomic():
        tenant = VEPCTenant.objects.select_for_update().filter(pk=pk)
        if not tenant:
            return
        tenant = tenant[0]
        tenant.manage_vhss()
        tenant.manage_vmme()
        tenant.manage_vmm()
        tenant.manage_vsm()
        tenant.manage_vsgwc()
        tenant.manage_vsgwu()
        tenant.manage_vpgwc()
        tenant.manage_vpgwu()
        tenant.cleanup_orphans()

