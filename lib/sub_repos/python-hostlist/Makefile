VERSIONED_FILES = hostlist.py hostlist hostlist.1 \
		  hostgrep hostgrep.1 \
		  dbuck dbuck.1 \
		  pshbak pshbak.1 \
		  setup.py python-hostlist.spec README
NON_VERSIONED_FILES = test COPYING MANIFEST.in CHANGES Makefile

NAME	= python-hostlist
VERSION = 1.23.0
RELEASE = 1

MOCK	= mock
MOCK_R = $(MOCK) $(if $(target),-r "$(target)")

all:
	@echo "Do:"
	@echo "  make tar  - build tar.gz source distribution"
	@echo "  make rpms - build RPMs using mock; results in ./packages"
	@echo "              variable ''target'' specifies mock chroot config"
	@echo "  make pypi - upload tar.gz to the Python Package Index"

prepare:
	$(RM) -r versioned
	mkdir versioned
	cp -pr $(NON_VERSIONED_FILES) versioned
	for f in $(VERSIONED_FILES); do sed -e "s/#VERSION#/$(VERSION)/" -e "s/#RELEASE#/$(RELEASE)/" <$$f >versioned/$$f; done

tar: prepare
	(cd versioned; make tar-versioned)

tar-versioned:
	python3 setup.py sdist

rpms: tar
	rpmbuild -ts -D"_srcrpmdir `pwd`/versioned/dist" --undefine="dist" \
		versioned/dist/$(NAME)-$(VERSION).tar.gz
	@# This will ask for root password twice (unless having mock privs)
	$(MOCK_R) --resultdir="./packages/$(shell basename $$(dirname $$($(MOCK_R) -p | egrep '^/')))" \
		--rebuild versioned/dist/$(NAME)-$(VERSION)-$(RELEASE).src.rpm

pypi: prepare
	(cd versioned; make pypi-versioned)

pypi-versioned:
	python3 setup.py sdist upload

clean:
	$(RM) -r versioned

.PHONY: test
test:
	PYTHONPATH=$(PWD) python2 test/test_hostlist.py
	PYTHONPATH=$(PWD) python3 test/test_hostlist.py
