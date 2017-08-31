from service import XOSService
from services.vepc.models import VEPCService

class XOSVEPCService(XOSService):
	provides = "tosca.nodes.VEPCService"
	xos_model = VEPCService
	copyin_props = ["view_url", "icon_url", "enabled", "published", "public_key", "private_key_fn", "versionNumber"]
