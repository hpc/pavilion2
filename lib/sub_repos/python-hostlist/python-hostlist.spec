%global srcname hostlist

%if 0%{?rhel} <= 8
# Support for python2 enabled by default. Pass --without python2 on command line
# when building to disable.
%bcond_without python2
%else
# Support for python2 disabled by default. Pass --with python2 on command line
# when building to enable.
%bcond_with python2
%endif

# Doesn't seem to be defined on el6, despite being referenced by other macros
%if !0%{?__python2:1}
%define __python2 /usr/bin/python2
%endif

# el8 complains if attempting to use the unversioned python_sitelib, and
# python2_sitelib is not defined on el6. Define it if needed
%if !0%{?python2_sitelib:1}
%define python2_sitelib %{python_sitelib}
%endif

# expansion of python2_sitelib errors on el8 without this
%define __python /usr/bin/python2

%if 0%{?el6}
%define py_shbang_opts -E
%else
%define py2_shbang_opts -E
%endif
%define py3_shbang_opts -E

%define extra_install_args --prefix /usr

Name:           python-%{srcname}
Version:        #VERSION#
Release:        #RELEASE#%{?dist}
Summary:        Python module for hostlist handling
Vendor:         NSC

Group:          Development/Languages
License:        GPL2+
URL:            http://www.nsc.liu.se/~kent/python-hostlist/
Source0:        http://www.nsc.liu.se/~kent/python-hostlist/%{name}-%{version}.tar.gz

BuildArch:      noarch

%global _description %{expand:
The hostlist.py module knows how to expand and collect hostlist
expressions.

The package also includes the 'hostlist' binary which can be used to
collect/expand hostlists and perform set operations on them, 'pshbak'
which collects output like 'dshbak' but using our hostlist library,
'hostgrep' which is a grep-like utility that understands hostlists,
and 'dbuck' which summarizes numerical data from multiple hosts.}

%description %_description

%if %{with python2}
%package -n python2-%{srcname}
Summary: %{summary}
%if 0%{?el8}
BuildRequires: python2-devel
%else
BuildRequires: python-devel
%endif
Provides: python-%{srcname} = %{version}-%{release}
Obsoletes: python-%{srcname} < 1.19-1

%description -n python2-%{srcname} %_description
%endif

%package -n python3-%{srcname}
Summary: %{summary}
BuildRequires: python%{python3_pkgversion}-devel

%description -n python3-%{srcname} %_description


%prep
%autosetup

%build
%py3_build
%if %{with python2}
%if 0%{?py2_build:1}
%py2_build
%else
# el6
%py_build
%endif
%endif


%install
rm -rf "$RPM_BUILD_ROOT"
%py3_install -- %{?extra_install_args}
%if %{with python2}
%if 0%{?py2_install:1}
%py2_install -- %{?extra_install_args}
%else
# el6
%py_install -- %{?extra_install_args}
%endif
%endif


%clean
rm -rf $RPM_BUILD_ROOT

%define _tool_files %{expand:
/usr/bin/hostlist
/usr/bin/hostgrep
/usr/bin/pshbak
/usr/bin/dbuck
%{_mandir}/man1/hostlist.1.gz
%{_mandir}/man1/hostgrep.1.gz
%{_mandir}/man1/pshbak.1.gz
%{_mandir}/man1/dbuck.1.gz
}

%if %{with python2}
%files -n python2-%{srcname}
%defattr(-,root,root,-)
%{python2_sitelib}/*
%doc README
%doc COPYING
%doc CHANGES
%_tool_files
%endif

%files -n python3-%{srcname}
%defattr(-,root,root,-)
%{python3_sitelib}/*
%{python3_sitelib}/__pycache__/*
%doc README
%doc COPYING
%doc CHANGES
%if !%{with python2}
%_tool_files
%endif


%changelog
* Wed Nov 30 2022 Torbjörn Lönnemark <ketl@nsc.liu.se> - 1.23.0-1
- Fix TypeError in Python 3 when collecting 'n n1'
- Build python2 packages on <= el8 by default

* Tue Oct 11 2022 Torbjörn Lönnemark <ketl@nsc.liu.se> - 1.22-1
- hostgrep: dynamically add characters allowed in hostnames.
- Make python2 support opt-in at build time

* Mon Oct 19 2020 Torbjörn Lönnemark <ketl@nsc.liu.se> - 1.21-1
- Fixes for building on el8

* Tue Jan 14 2020 Kent Engström <kent@nsc.liu.se> - 1.20-1
- Adapt to Python 3 stricter comparison rules
- Fix Python 2+2 support for hostgrep, pshbak, dbuck

* Mon Sep 30 2019 Torbjörn Lönnemark <ketl@nsc.liu.se> - 1.19-1
- dbuck: Don't print hostlist padding for empty buckets

* Thu Jun 21 2018 Kent Engström <kent@nsc.liu.se> - 1.18-1
- Accept whitespace in hostlists passed as arguments
- Support both Python 2 and Python 3 natively

* Mon Jan 23 2017 Kent Engström <kent@nsc.liu.se> - 1.17-1
- New features in dbuck by cap@nsc.liu.se:
- Add option -z, --zero
- Add option -b, --bars
- Add option --highligh-hostlist and --color
- Add option -a, --anonymous
- Add option -p, --previous and --no-cache
- Also other fixes and cleanups in dbuck

* Mon May 23 2016 Kent Engström <kent@nsc.liu.se> - 1.16-1
- Ignore PYTHONPATH et al. in installed scripts

* Thu Apr 21 2016 Kent Engström <kent@nsc.liu.se> - 1.15-1
- Add missing options to the hostgrep(1) man page.
- Add --restrict option to hostgrep.
- Add --repeat-slurm-tasks option.
- dbuck: major rewrite, add -r/-o, remove -b/-m
- dbuck: add a check for sufficient input when not using -k
- dbuck: Fix incorrect upper bound of underflow bucket
