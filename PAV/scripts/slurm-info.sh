#!/bin/sh
## Library of functions to determine SLURM state

shopt -s nullglob

local_info=$(dirname $BASH_SOURCE)/site/slurm_info.local.sh
if [ -f $local_info ]; then
    source $local_info
    PARTITION=$(get_partition)
    ACCOUNT=$(get_account)
    QOS=$(get_qos)
    RESERVATION=$(get_reservation)
    FEATURES="$(get_features)"
else
    PARTITION=
    ACCOUNT=
    QOS=
    RESERVATION=
    FEATURES=
fi


function slurm_list_to_sequence() {
    ## Given a SLURM-style node listing and an optional list of excluded nodes,
    ##  return a space-separated list of node numbers
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


function get_slurm_state() (
    ## Discover the current usability of a cluster partition,
    ##  return a sequence of cluster size, availability, allocated, and
    ##  an available-node list
    local partition=${1:-$PARTITION}

    local s_idx=4
    local l_idx=6
    if isCray; then
	s_idx=7
	l_idx=9
    fi
    local size=$(sinfo -a -o '%P %.6D' | grep $partition | \
        awk "{ print \$2 }" | paste -sd+ - | bc)
    local unavail=$(sinfo -SN -Ro '%P %.16n %.6t' | grep $partition | \
        grep -v alloc | grep -v "maint\*" | wc -l)
    local avail=$(sinfo -SN -o '%P %.6D %.6t %N' | grep $partition | \
        grep -v alloc | grep -v down | grep -v drain | grep -v "maint\*" | \
        awk "{ print \$2 }" | paste -sd+ - | bc)
    avail=$(echo "$avail-$unavail" | bc)
    local bad_list=$(sinfo -SN -Ro '%P %.16n %.6t' | grep $partition | \
        grep -v alloc | grep -v "maint\*" | awk "{ print \$2 }" | paste -sd, -)
    local list=$(sinfo -SN -o '%P %.6D %.6t %N' | grep $partition | \
        grep -v alloc | grep -v down | grep -v "maint\*" | \
        awk "{ print \$4 }" | paste -sd, -)
    local allocd=$(sinfo -SN -o '%P %.6D %.6t %N' | grep $partition | \
        grep alloc | grep -v down | grep -v "maint\*" | \
        awk "{ print \$2 }" | paste -sd+ - | bc)

    if [[ "$size" == "" ]] || [ "$size" -lt "1" ]; then
	size=0
    fi
    if [[ "$avail" == "" ]] || [ "$avail" -lt "1" ]; then
        exit 16  # EBUSY
    fi
    if [[ "$allocd" == "" ]] || [ "$allocd" -lt "1" ]; then
        allocd=0
    fi
    echo $size $avail $allocd "$list"
    exit 0
)


function nodes_status() {
    ## Discovers and confirms up-status of available nodes
    local partition=${1:-$PARTITION}
    local account=${2:-$ACCOUNT}
    local qos=${3:-$QOS}
    local reservation=${4:-$RESERVATION}
    local features=${5:-"$FEATURES"}
    local excludes=$6
    local quiet=${7:-0}

    local slurm_args=""
    if [[ "$partition" != "" ]]; then
        slurm_args="$slurm_args --partition=$partition"
    fi
    if [[ "$account" != "" ]]; then
        slurm_args="$slurm_args --account=$account"
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

    local state=$(get_slurm_state $partition)
    local retval=$?
    if [ "$retval" -ne "0" ]; then
    	if [ "$quiet" -ne "0" ]; then
	    echo "ERROR: too few nodes available"
	    sinfo | grep $partition | grep -v alloc | grep -v down
	fi
	exit $retval
    fi
    local size=$(echo $state | cut -d ' ' -f 1)
    local avail=$(echo $state | cut -d ' ' -f 2)
    local allocd=$(echo $state | cut -d ' ' -f 3)
    local list=$(echo "$state" | cut -d ' ' -f 4)
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
        #salloc -w $node_id $slurm_args $immediate echo -n 'OK' #2>/dev/null
        echo
    done
}


function bad_nodes() {
    nodes_status $@ | grep -v OK
}


function good_nodes() {
    nodes_status $@ #| grep OK
}


## if called, not sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    state=$(get_slurm_state $@)
    good_nodes $@
    echo "$(good_nodes $@ | wc -l)/$(echo $state | cut -d ' ' -f 1) nodes"
fi
