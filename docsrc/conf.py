from photon_platform.publish.global_conf import *
import geometor.seer_navigator as module

version = module.__version__

org = "geometor"
org_name = "GEOMETOR"

repo = "seer_navigator"
repo_name = "seer_navigator"

setup_globals(org, org_name, repo, repo_name)

site_title = "SEER Navigator"
project = site_title
html_title = f"{site_title} • {org_name}"
