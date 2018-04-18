## Library of functions to determine SLURM state

shopt -s nullglob

# Globals
default_PARTITION=standard
KNL_PARTITION=knl
default_QOS=hpctest
default_RESERVATION=
DST_RESERVATION=PreventMaint
default_FEATURES=
KNL_FEATURES="quad cache"


function onDST() {
    grep "DST Underway" /etc/motd >/dev/null && return 0 || return 1
}


function isCray() {
    [[ -f /etc/opt/cray/release/cle-release ]] && return 0 || return 1
}


function get_reservation() {
    if onDST; then
        echo $DST_RESERVATION
    else
        echo $default_RESERVATION
    fi
}


function get_features() {
    local partition=${1:-$default_PARTITION}
    if [[ "$partition" == "$KNL_PARTITION" ]]; then
        echo $KNL_FEATURES
    else
        echo $default_FEATURES
    fi
}



function get_node_sequence() {
    ## Given a SLURM-style node listing and an optional list of excluded nodes,
    ##  return a space-separated list of node hostnames
    local nlist=$1
    local excluded=$2

    partial=${nlist#*[}
    partial=${partial%]}

    while [[ "$partial" != "" ]]; do
	partial=${partial#,}
	current=${partial%%,*}
	start=${current%-*}
	end=${current#*-}
	end=${end%,*}
	for node in $(seq $start $end); do
	    found=0
	    for ex in $excluded; do
		if [[ "$node" == "$ex" ]]; then
		    found=1
		fi
	    done
	    if [ "$found" -eq "0" ]; then
		node_list="$node_list $node"
	    fi
	done
	partial=${partial#$current}
    done
    echo $node_list
}


function slurm_list_to_sequence() {
    ## Given a SLURM-style node listing, return the sequence of node numbers
    local slist=${1#*[}
    slist=${slist%]*}
    slist=$(echo "$slist" | sed 's/,/ /g' |
                sed 's/\([0-9]*\)-\([0-9]*\)/\1:\2/g')
    local nlist=""    
    for node in $slist; do
	if [[ "$node" == *":"* ]]; then
	    first=${node%:*}
	    last=${node#*:}
	    nlist="$nlist $(seq -s ' ' $first $last)"
	else
	    nlist="$nlist $node"
	fi
    done
    echo $nlist
}


function get_slurm_state() {
    ## Discover the current usability of a cluster partition,
    ##  return a sequence of cluster size, availability, allocated, and
    ##  an available-node list
    local partition=${1:-$default_PARTITION}
    
    local s_idx=4
    local l_idx=6
    if isCray; then
	s_idx=7
	l_idx=9
    fi
    local size=$(sinfo | grep $partition | \
                     awk "{ print \$$s_idx }" | paste -sd+ - | bc)
    local avail=$(sinfo | grep $partition | \
                     grep -v alloc | grep -v down | grep -v "maint\*" | \
                     awk "{ print \$$s_idx }" | paste -sd+ - | bc)
    local list=$(sinfo | grep $partition | \
                     grep -v alloc | grep -v down | grep -v "maint\*" | \
                     awk "{ print \$$l_idx }" | paste -sd, -)
    local allocd=$(sinfo | grep $partition | \
                       grep alloc | grep -v down | grep -v "maint\*" | \
                       awk "{ print \$$s_idx }" | paste -sd+ - | bc)

    if [[ "$avail" == "" ]] || [ "$avail" -lt "1" ]; then
        return 16  # EBUSY
    fi
    echo $size $avail $allocd "$list"
    return 0
}


function nodes_status() {
    ## Discovers and confirms up-status of available nodes
    local partition=${1:-$default_PARTITION}
    local qos=${2:-$default_QOS}
    local reservation=${3:-$(get_reservation)}
    local features=${4:-"$(get_features)"}
    local excludes=$5
    local quiet=${6:-0}

    local slurm_args=""
    if [[ "$partition" != "" ]]; then
        slurm_args="$slurm_args --partition=$partition"
    else
        partition=$default_PARTITION
    fi
    if [[ "$features" != "" ]]; then
        for feature in $features; do
	    slurm_args="$slurm_args -C $feature"
        done
    fi
    if [[ "$reservation" != "" ]]; then
        slurm_args="$slurm_args --reservation=$reservation"
    fi
    if [[ "$qos" != "" ]]; then
        slurm_args="$slurm_args --qos=$qos"
    fi

    local state = ($(get_slurm_state $partition))
    local retval = $?
    if [ "$retval" -ne "0" ]; then
    	if [ "$quiet" -ne "0" ]; then
	    echo "ERROR: too few nodes available"
	    sinfo | grep $partition | grep -v alloc | grep -v down
	fi
	exit $retval
    fi
    local size = state[0]
    local avail = state[1]
    local allocd = state[2]
    local list = state[3]
    
    local available_nodes=($(get_node_sequence "$list" "$excludes"))
    local num_nodes=${#available_nodes[@]}
    
    local immediate=""
    if onDST; then
        immediate="-I"
    fi

    local magnitude=$(printf %.0f $(echo "l($size)/l(10)" | bc -l))
    if isCray; then
	magnitude=5
    fi

    local fe=$(hostname)
    local sys=${fe%-*}
    for idx in $(slurm_list_to_sequence "$list"); do
        local node_id=$(printf ${sys}%0${magnitude}d $idx)
        echo -n "$node_id "
        salloc -w $node_id $slurm_args $immediate echo -n 'OK' 2>/dev/null
        echo
    done
}


function bad_nodes() {
    nodes_status $@ | grep -v OK
}


function good_nodes() {
    nodes_status $@ | grep OK
}
