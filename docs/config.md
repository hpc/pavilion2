# Configuring Pavilion

Pavilion is driven largely by configurations:
  - The [pavilion.yaml](#pavilion.yaml) file sets global pavilion settings.
  - [Test Configs](tests/basics.md) for defining tests.
  - [Host Configs](tests/basics.md#host-configs) for setting host defaults for 
  tests.
  - [Mode Configs](tests/basics.md#mode-configs) for addition test default sets.
  - [Plugins](plugins/basics.md) allow you to customize pavilion beyond just 
  configs.

## Config Directories 
Pavilion looks for configs in the following hierarchy by default, and uses 
the first one it finds. 

  - The current directory
  - The user's home directory
  - The directory given via the `PAV_CONFIG_DIR` environment variable.
  - The Pavilion lib directory __(don't put configs here)__

Each config directory can (optionally) have any of the sub-directories shown 
here.

![Config Directory Layout](imgs/config_dir.png "Pavilion Config Directory")

## Pavilion.yaml
Pavilion looks for a `pavilion.yaml` in the default config hierarchy, and 
uses the first one it finds. 

It's ok to run pavilion without a config; the defaults should be good enough 
in many cases.

### Generating a pavilion.yaml template
Pavilion can print template files, with documentation, for all of it's config
files. In this case, use the command `pav show config --template`. Since all 
config values are optional, you can just use the pieces you need.

### Setting You Should Set
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
