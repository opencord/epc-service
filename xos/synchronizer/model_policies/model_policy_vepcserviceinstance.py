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
from synchronizers.new_base.model_policies.model_policy_tenantwithcontainer import TenantWithContainerPolicy, LeastLoadedNodeScheduler
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

class VEPCServiceInstancePolicy(TenantWithContainerPolicy):
    model_name = "VEPCServiceInstance"

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

    def create_service_instance(si):
        service = self.get_service_for_service_instance(si)
	if not service:
	    raise Exception('No service object for %s'%service)

	si_class = getattr(Slice().stub, si)
	s = si_class(owner = service, name = 'epc-' + si.lower())
	s.master_serviceinstance = self.obj

	self.configure_service_instance(s)
	s.save()
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
                self.create_link(src, k)

    def create_child_services(self, service_instance):
        self.obj = service_instance
        # Create service graph based on blueprint
        chosen_blueprint = service_instance.blueprint
        try:
            blueprint = next(b for b in blueprints if b['name'] == chosen_blueprint)
        except StopIteration:
            log.error('Chosen blueprint (%s) not found' % chosen_blueprint)

        self.recursive_create_links(blueprint['graph'], None)

    def handle_update(self, service_instance):
        self.create_child_services(service_instance)

        if (service_instance.link_deleted_count > 0) and (not service_instance.provided_links.exists()):
            self.logger.info(
                "The last provided link has been deleted -- self-destructing.")
            self.handle_delete(service_instance)
            if VEPCServiceInstance.objects.filter(id=service_instance.id).exists():
                service_instance.delete()
            else:
                self.logger.info("Tenant %s is already deleted" %
                                 service_instance)
            return

        self.manage_container(service_instance)

    def handle_delete(self, service_instance):
        if service_instance.instance and (not service_instance.instance.deleted):
            all_service_instances_this_instance = VEPCServiceInstance.objects.filter(
                instance_id=service_instance.instance.id)
            other_service_instances_this_instance = [
                x for x in all_service_instances_this_instance if x.id != service_instance.id]
            if (not other_service_instances_this_instance):
                self.logger.info(
                    "VEPCServiceInstance Instance %s is now unused -- deleting" % service_instance.instance)
                self.delete_instance(
                    service_instance, service_instance.instance)
            else:
                self.logger.info("VEPCServiceInstance Instance %s has %d other service instances attached" % (
                    service_instance.instance, len(other_service_instances_this_instance)))

    def get_service(self, service_instance):
        service_name = service_instance.owner.leaf_model_name
        service_class = globals()[service_name]
        return service_class.objects.get(id=service_instance.owner.id)

    def find_instance_for_instance_tag(self, instance_tag):
        tags = Tag.objects.filter(name="instance_tag", value=instance_tag)
        if tags:
            return tags[0].content_object
        return None

    def find_or_make_instance_for_instance_tag(self, service_instance):
        instance_tag = self.get_instance_tag(service_instance)
        instance = self.find_instance_for_instance_tag(instance_tag)
        if instance:
            if instance.no_sync:
                # if no_sync is still set, then perhaps we failed while saving it and need to retry.
                self.save_instance(service_instance, instance)
            return instance

        desired_image = self.get_image(service_instance)
        desired_flavor = self.get_flavor(service_instance)

        slice = service_instance.owner.slices.first()

        (node, parent) = LeastLoadedNodeScheduler(slice, label=None).pick()

        assert (slice is not None)
        assert (node is not None)
        assert (desired_image is not None)
        assert (service_instance.creator is not None)
        assert (node.site_deployment.deployment is not None)
        assert (desired_image is not None)

        instance = Instance(slice=slice,
                            node=node,
                            image=desired_image,
                            creator=service_instance.creator,
                            deployment=node.site_deployment.deployment,
                            flavor=flavors[0],
                            isolation=slice.default_isolation,
                            parent=parent)

        self.save_instance(service_instance, instance)

        return instance

    def manage_container(self, service_instance):
        if service_instance.deleted:
            return

        if service_instance.instance:
            # We're good.
            return

        instance = self.find_or_make_instance_for_instance_tag(
            service_instance)
        service_instance.instance = instance
        # TODO: possible for partial failure here?
        service_instance.save()

    def delete_instance(self, service_instance, instance):
        # delete the `instance_tag` tags
        tags = Tag.objects.filter(service_id=service_instance.owner.id, content_type=instance.self_content_type_id,
                                  object_id=instance.id, name="instance_tag")
        for tag in tags:
            tag.delete()

        tags = Tag.objects.filter(content_type=instance.self_content_type_id, object_id=instance.id,
                                  name="vm_vrouter_tenant")
        for tag in tags:
            address_manager_instances = list(
                ServiceInstance.objects.filter(id=tag.value))
            tag.delete()

            # TODO: Potential partial failure

            for address_manager_instance in address_manager_instances:
                self.logger.info(
                    "Deleting address_manager_instance %s" % address_manager_instance)
                address_manager_instance.delete()

        instance.delete()

    def save_instance(self, service_instance, instance):
        instance.volumes = "/etc/dnsmasq.d,/etc/ufw"
        instance.no_sync = True   # prevent instance from being synced until we're done with it
        super(VEPCServiceInstancePolicy, self).save_instance(instance)

        try:
            if instance.isolation in ["container", "container_vm"]:
                raise Exception("Not supported")

            instance_tag = self.get_instance_tag(service_instance)

            if instance_tag:
                tags = Tag.objects.filter(
                    name="instance_tag", value=instance_tag)
                if not tags:
                    tag = Tag(service=service_instance.owner, content_type=instance.self_content_type_id,
                              object_id=instance.id, name="instance_tag", value=str(instance_tag))
                    tag.save()

            instance.no_sync = False   # allow the synchronizer to run now
            super(VEPCServiceInstancePolicy, self).save_instance(instance)
        except:
            # need to clean up any failures here
            raise

    def get_instance_tag(self, service_instance):
        return '%d'%service_instance.id

    def get_image(self, service_instance):
        return None

    def get_flavor(self, service_instance):
        raise None

