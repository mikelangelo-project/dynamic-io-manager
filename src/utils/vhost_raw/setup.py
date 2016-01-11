from setuptools import Extension, setup, find_packages
packages = find_packages()

extensions = {
    "vhost_raw": ["vhost_raw.c", "vhost_mapper.c", "kernel_mapper.c"],
    "uptime": ["uptime.c"],
    "kernel_mapper": ["counter.c", "kernel_mapper.c"]
}
ext_modules = [Extension(key, sources=sources)
               for key, sources in extensions.items()]
print ext_modules
setup(name="raw_extensions", author="Eyal Moscocvici", version="0.1",
      packages=packages, ext_modules=ext_modules)
