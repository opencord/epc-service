# Copyright 2017-present Open Networking Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from synchronizers.new_base.modelaccessor import *
from synchronizers.new_base.model_policies.model_policy_tenantwithcontainer import Policy
from synchronizers.new_base.exceptions import *

from xosconfig import Config
from multistructlog import create_logger

log = create_logger(Config().get('logging'))
blueprints = Config().get('blueprints')

def service_of_service_instance(si):
    if si.endswith('Tenant'): 
        return si[:-len('Tenant')] + 'Service'
    elif si.endswith('ServiceInstance'): 
        return si[:-len('ServiceInstance')] + 'Service'
    else:
        raise Exception('Could not translate service instance into service: %s'%si)

class VEPCServiceInstancePolicy(Policy):
    model_name = "VEPCServiceInstance"

    def __init__(self):
        self.in_memory_instances = []
        super(VEPCServiceInstancePolicy, self).__init__()

    """TODO: Update the following to not be service-specific
       This code assumes there is only one vendor installed 
    """
    def configure_service_instance(self, service_instance):
        if service_instance.leaf_model_name == 'VSPGWUTenant':
            vendor = VSPGWUVendor.objects.first()
            if not vendor:
                raise Exception('No VSPGWU vendors')
            service_instance.vspgwu_vendor = vendor
        elif service_instance.leaf_model_name == 'VSPGWCTenant':
            vendor = VSPGWCVendor.objects.first()
            if not vendor:
                raise Exception('No VSPGWC vendors')
            service_instance.vspgwc_vendor = vendor

    def child_service_instance_from_name(self, name):
        service_instances = self.obj.child_serviceinstances.all() 
        service_instances.extend(self.in_memory_instances)

        try:
            service_instance = next(s for s in service_instances if s.leaf_model_name == name)
        except StopIteration:
            service_instance = None

        return service_instance 

    def get_service_for_service_instance(self, si):
        service = service_of_service_instance(si)
        service_class = getattr(Slice().stub, service)
        service_obj = service_class.objects.first() # There's only one service object
        return service_obj

    def create_service_instance(self, si):
        service = self.get_service_for_service_instance(si)
	if not service:
	    raise Exception('No service object for %s'%service)

	si_class = getattr(Slice().stub, si)
	s = si_class(owner = service, name = 'epc-%s-%d'%(si.lower(), self.obj.id))
	s.master_serviceinstance = self.obj

	self.configure_service_instance(s)
	s.save()

        self.in_memory_instances.append(s)
        return s

    def create_link(self, src, dst):
        src_instance = self.child_service_instance_from_name(src)
        if not src_instance:
            src_instance = self.create_service_instance(src)

        dst_instance = self.child_service_instance_from_name(dst)
        if not dst_instance:
            dst_instance = self.create_service_instance(dst)
      
        src_service = self.get_service_for_service_instance(src)
        dst_service = self.get_service_for_service_instance(dst)

        service_dependency = ServiceDependency.objects.filter(provider_service_id = dst_service.id, subscriber_service_id = src_service.id)
        if not service_dependency:
            service_dependency = ServiceDependency(provider_service = dst_service, subscriber_service = src_service)
            service_dependency.save()

        service_instance_link = ServiceInstanceLink.objects.filter(provider_service_instance_id = dst_instance.id, subscriber_service_instance_id = src_instance.id)
        if not service_instance_link:
            service_instance_link = ServiceInstanceLink(provider_service_instance = dst_instance, subscriber_service_instance = src_instance)
            service_instance_link.save()

    def recursive_create_links(self, blueprint, src):
	for k, v in blueprint.iteritems():
	    if src:
		self.create_link(src, k)

	    if isinstance(v, dict):
		self.recursive_create_links(v, k)
	    else:
		self.create_link(k, v)

    def create_child_services(self, service_instance):
        self.obj = service_instance
        # Create service graph based on blueprint
        chosen_blueprint = service_instance.blueprint
        try:
            blueprint = next(b for b in blueprints if b['name'] == chosen_blueprint)
        except StopIteration:
            log.error('Chosen blueprint (%s) not found' % chosen_blueprint)

        self.recursive_create_links(blueprint['graph'], None)

    def handle_create(self, service_instance):
        self.handle_update(service_instance)

    def handle_update(self, service_instance):
        self.create_child_services(service_instance)

    def handle_delete(self, service_instance):
	raise Exception("Not implemented")
