from setuptools import Extension, setup, find_packages
packages = find_packages()

extensions = {
    "vhost_raw": ["vhost_raw.c", "vhost_mapper.c", "copy_to_user.c"],
    "uptime": ["uptime.c"],
    # "kernel_mapper": ["counter.c", "copy_to_user.c"]
}
ext_modules = [Extension(key, sources=sources)
               for key, sources in extensions.items()]
print ext_modules
setup(name="raw_extensions", author="Eyal Moscocvici", version="0.1",
      packages=packages, ext_modules=ext_modules)
