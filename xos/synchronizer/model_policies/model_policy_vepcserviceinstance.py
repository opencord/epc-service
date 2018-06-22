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


class VEPCServiceInstancePolicy(Policy):
    model_name = "VEPCServiceInstance"

    def get_service_object(self, name):
        """ return: First Service object """
        if any(map(lambda x: x in name, ["ServiceInstance", "Tenant"])):
            name = name.replace("ServiceInstance", "Service")
            name = name.replace("Tenant", "Service")

        service_obj = getattr(Slice().stub, name).objects.first()

        if not service_obj:
            raise Exception("No %s object existed." % name)

        return service_obj

    def get_tenant_class(self, name):
        """
        return: Tenant class
        We need to claim new Tenant instance(object) by this class
        """
        if not name.endswith("Service"):
            raise Exception("Tenant object needs to find with Service name.")

        if hasattr(Slice().stub, name + "Instance"):
            tenant_class = getattr(Slice().stub, name + "Instance")
        elif hasattr(Slice().stub, name.replace("Service", "Tenant")):
            tenant_class = getattr(Slice().stub, name.replace("Service", "Tenant"))
        else:
            raise Exception("No %s class existed." % name)

        return tenant_class

    def get_vendor_object(self, name):
        postfixs = ["Service", "ServiceInstance", "Tenant"]
        if not any(map(lambda x: name.endswith(x), postfixs)):
            raise Exception("Vendor object need to find with Service or Tenant name.")

        for postfix in postfixs:
            name = name.replace(postfix, "Vendor")

        vendor_obj = getattr(Slice().stub, name).objects.first()

        if not vendor_obj:
            raise Exception("No %s object existed." % name)

        return vendor_obj

    def create_service_instance(self, service_obj, node_label=None):
        tenant_class = self.get_tenant_class(service_obj.leaf_model_name)
        vendor_obj = self.get_vendor_object(service_obj.leaf_model_name)

        vendor_name = "%s_vendor" % service_obj.name.lower()
        name = "epc-%s-%d" % (tenant_class.__name__.lower(), self.obj.id)

        instance = tenant_class.objects.filter(owner=service_obj.id, name=name).first()

        if instance:
            return instance

        instance = tenant_class(owner=service_obj, name=name)
        instance.master_serviceinstance = self.obj
        instance.__setattr__(vendor_name, vendor_obj)

        if node_label:
            instance.node_label = "%s-%d" % (node_label, self.obj.id)

        # Assign custom parameter to child tenant
        if name in ["vspgwc", "vspgwu"]:
            instance.enodeb_ip_addr = self.obj.enodeb_ip_addr_s1u
            instance.enodeb_mac_addr = self.obj.enodeb_mac_addr_s1u
            instance.appserver_ip_addr = self.obj.appserver_ip_addr
            instance.appserver_mac_addr = self.obj.appserver_mac_addr
        elif name in ["vmme"]:
            instance.enodeb_ip_addr = self.obj.enodeb_ip_addr_s1mme

        instance.no_sync = True
        instance.no_policy = True
        instance.invalidate_cache(vendor_name)

        instance.save()

        log.info("Instance %s was created." % instance)

        return instance

    def create_network(self, network):
        name = network.get("name", "")
        owner = network.get("owner", "")
        site_name = self.obj.site.login_base
        template_name = network.get("template", "public")
        subnet = network.get("subnet", "")
        permit_all_slices = network.get("permit_all_slices", False)

        # Get Network, If Network subnet mismatch, then update
        # If Network existed, then early return.
        network_obj = Network.objects.filter(name=name).first()
        if network_obj:
            if network_obj.subnet != subnet:
                network_obj.subnet = subnet
                network_obj.save()
            return network_obj

        # Get Network Template by assigned name.
        template = NetworkTemplate.objects.filter(name=template_name).first()
        if not template:
            raise Exception("Template %s for network %s is not exist." % (template_name, name))

        # Get Network owner slice by assigned name.
        slice_name = "%s_%s" % (site_name, owner)
        owner_slice = Slice.objects.filter(name=slice_name).first()
        if not owner_slice:
            raise Exception("Owner Slice %s for network %s is not exist." % (owner, name))

        # Create Network Instance and save.
        network = Network(name=name, subnet=subnet, template=template,
                          permit_all_slices=permit_all_slices, owner=owner_slice)
        network.save()

        log.info("Network %s was created." % network)

        return network

    def create_service_dependency(self, source, target):
        """
        Create Service Dependency object for Connectivity between service
        source: source service object
        target: target service object
        """

        # Use Subscriber and Provider's ID to get Dependency
        dependency = ServiceDependency.objects.filter(
            subscriber_service_id=source.id, provider_service_id=target.id
        ).first()

        if not dependency:
            # If no dependency existed, then create dependency
            dependency = ServiceDependency(
                subscriber_service=source, provider_service=target
            )
            dependency.save()

            log.info("Service dependency %s was created, %s->%s" % (dependency, source, target))

        # Get subscriber and provider's Service Instance
        source_tenant_class = self.get_tenant_class(source.leaf_model_name)
        target_tenant_class = self.get_tenant_class(target.leaf_model_name)
        source_tenants = source_tenant_class.objects.all()
        target_tenants = target_tenant_class.objects.all()

        # Use cross product to create ServiceInstance Link
        for source_tenant in source_tenants:
            for target_tenant in target_tenants:
                link = ServiceInstanceLink.objects.filter(
                    subscriber_service_instance_id=source_tenant.id,
                    provider_service_instance_id=target_tenant.id
                )

                if not link:
                    link = ServiceInstanceLink(
                        subscriber_service_instance=source_tenant,
                        provider_service_instance=target_tenant
                    )

                    link.save()

                    log.info("Service instance link %s was created" % link)

        return dependency

    def assign_network_to_service(self, service, network):
        service_slice = service.slices.first()
        network_slice = NetworkSlice.objects.filter(
            network=network.id, slice=service_slice.id
        )

        if not network_slice:
            network_slice = NetworkSlice(
                network=network, slice=service_slice
            )
            network_slice.save()

        return network_slice

    def create_services_from_blueprint(self, blueprint):
        dependencies = list()
        instances = list()

        for network in blueprint["networks"]:
            network_instance = self.create_network(network)

        for node in blueprint["graph"]:
            # Get Service's Name, Network, Link attribute from blueprint node
            # If value is not set, return empty data struct instead.
            tenant_str = node.get("name", "")
            networks = node.get("networks", list())
            links = node.get("links", list())
            node_label = node.get("node_label", None)

            # Get Service Class by Defined Service Instance Name
            # service_obj: Service Object in XOS core
            # tenant_obj: Tenant Object in XOS core
            service_obj = self.get_service_object(tenant_str)

            for network in networks:
                network_obj = Network.objects.filter(name=network).first()
                self.assign_network_to_service(service_obj, network_obj)

            instance = self.create_service_instance(service_obj, node_label=node_label)
            instances.append(instance)

            # Collect Service Dependencies relationship from links
            for provider in links:
                provider_str = provider.get("name", "")
                provider_service_obj = self.get_service_object(provider_str)
                dependencies.append((service_obj, provider_service_obj))

        log.info("Dependency Pair: %s" % dependencies)

        # Create Service Dependency between subscriber and provider
        for subscriber, provider in dependencies:
            self.create_service_dependency(subscriber, provider)

        for instance in instances:
            instance.no_policy = False
            instance.no_sync = False
            instance.save()

    def handle_create(self, service_instance):
        self.handle_update(service_instance)

    def handle_update(self, service_instance):
        # Register EPC-Service's service_instance as self.obj
        self.obj = service_instance

        blueprint_name = service_instance.blueprint
        try:
            blueprint = filter(lambda x: x["name"] == blueprint_name, blueprints)[0]
        except StopIteration:
            log.error("Chosen blueprint: %s not defined" % blueprint_name)

        self.create_services_from_blueprint(blueprint)
