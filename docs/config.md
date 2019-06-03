# Configuring Pavilion

Pavilion looks for a `pavilion.yaml` in the following locations, and uses the
 first one it finds:
 
  - The current directory
  - The user's home directory
  - The directory given via the `PAV_CONFIG_DIR` environment variable.
  - The Pavilion lib directory __(don't put configs here)__

It's ok to run pavilion without a config; the defaults should be good enough 
in many cases.

## Generating a pavilion.yaml template
Pavilion can print template files, with documentation, for all of it's config
files. In this case, use the command `pav show config --template`. Since all 
config values are optional, you can just use the pieces you need.

## Setting You Should Set
While everything is optional, these are some things you probably want to set.

#### working_dir
This determines where your test run information is 
stored. If you don't set this, everyone will have a separate history in 
`$HOME/.pavilion/working_dir`.

#### shared_group
If you have a shared working directory, you need a 
shared group to share those files. Pavilion will automatically write all 
files as this group.

#### result_log 
The result log holds all the result json for every test you
run. If you want to feed that into splunk, you may want to specify where to 
write it. 

#### proxies
Pavilion can auto-download and update source for tests, but 
 it needs to be able to get to the internet. 
 
```yaml
proxies:
    http: myproxy.example.com:8080
    https: myproxy.example.com: 8080

no_proxy:
  - example.com
  - alsolocal.com
```
 
## Config Directories
Pavilion searches the above hierarchy of config directories in the order
for test suites, plugins, and more. For most files, the first file found is 
used. Plugins follow a different set of behaviors, depending on the plugin.

###Layout

 - `tests/` - For test suites. The file name (without .yaml) is the suite 
 name. 
 - `hosts/` - For host configs. The file name (without .yaml) is the host 
 name matched against the `sys_name` var when looking up hosts.
 - `modes/` - For mode configs. The file name (with .yaml) is the mode name.
 - `test_src/` - Test source files are looked for here.
 - `plugins/` - Plugins go here. It's suggested you use the following hierarchy
  to organize plugins, but it is optional. In reality, the entire plugins 
  directory tree is searched, and the plugin class determines the plugin type.
   - `sys/` - System variable plugins.
   - `modules/` - Module wrapper plugins.
   - `results/` - Result parser plugins.
   - `sched/` - Scheduler plugins.
   - `commands/` - Command plugins.
