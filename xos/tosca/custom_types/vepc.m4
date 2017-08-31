tosca_definitions_version: tosca_simple_yaml_1_0

# compile this with "m4 vepc.m4 > vepc.yaml"

# include macros
include(macros.m4)

node_types:
    tosca.nodes.VEPCService:
        derived_from: tosca.nodes.Root
        description: >
            VEPC Service
        capabilities:
            xos_base_service_caps
        properties:
            xos_base_props
            xos_base_service_props

    tosca.nodes.VEPCTenant:
        derived_from: tosca.nodes.Root
        description: >
            VEPC Tenant
        properties:
            xos_base_tenant_props
            description:
                type: string
                required: false
            has_vhss:
                type: boolean
                required: true            
            has_vmme:
                type: boolean
                required: true            
            has_vmm:
                type: boolean
                required: true            
            has_vsm:
                type: boolean
                required: true            
            has_vsgwc:
                type: boolean
                required: true            
            has_vsgwu:
                type: boolean
                required: true            
            has_vpgwc:
                type: boolean
                required: true            
            has_vpgwu:
                type: boolean
                required: true            

