#%Module

puts stderr [module-info name]

regexp {^([^/]*)} [module-info name] mname1 module_name
regexp {/([^/]*)$} [module-info name] mname1 module_version
if { ! [info exists module_version] } {
    set module_version ""
}

append-path TEST_MODULE_NAME ${module_name}
append-path TEST_MODULE_VERSION ${module_version}
