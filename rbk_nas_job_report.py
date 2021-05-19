#!/usr/bin/python
from __future__ import print_function
import rubrik_cdm
import sys
import getopt
import getpass
import datetime
import pytz
import pprint
import ast
import urllib3
urllib3.disable_warnings()

def usage():
    sys.stderr.write("Usage: rbk_nas_job_report.py [-hDv] [-o output_file] [-c creds] [-t token] rubrik\n")
    sys.stderr.write("-h | --help : Prints this message\n")
    sys.stderr.write("-D | --DEBUG : Prints a lot of debug information for the developer\n")
    sys.stderr.write("-v | --verbose : Prints progress messages while the script runs\n")
    sys.stderr.write("-o | --outout= : Specify an output file for the report (csv format)\n")
    sys.stderr.write("-c | --creds= : Specify the creds on the CLI. By default the user is prompted\n")
    sys.stderr.write("-t | --token= : Specify an API token instead of credentials\n")
    sys.stderr.write("rubrik : Name or IP of a Rubrik node\n")
    exit(0)

def dprint(message, pf):
    if DEBUG:
        if not pf:
            print(message)
        else:
            pp.pprint(message)

def vprint(message):
    if VERBOSE:
        print(message)

def python_input(message):
    if int(sys.version[0]) > 2:
        val = input(message)
    else:
        val = raw_input(message)
    return(val)

def oprint(message, fh):
    if not fh:
        print(message, end='')
    else:
        fh.write(message)

def get_scan_rate(event_series):
    for det in event_series['eventDetailList']:
        if det['eventName'] != "Fileset.FilesetMetadataScanFinished":
            continue
        det_info = ast.literal_eval(det['eventInfo'])
        return(det_info['params']['${scanRate}'])

def byte_convert(size,precision=1):
    suffixes=['B','KB','MB','GB','TB']
    suffixIndex = 0
    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1 #increment the index of the suffix
        size = size/1024.0 #apply the division
    return "%.*f%s"%(precision,size,suffixes[suffixIndex])

if __name__ == "__main__":
    user = ""
    password = ""
    rubrik_host = ""
    DEBUG = False
    VERBOSE = False
    delim = ","
    ofh = ""
    outfile = ""
    token = ""
    timeout = 60
    pp = ""
    share_list = {}
    fs_list = []

    optlist, args = getopt.getopt(sys.argv[1:], 'hDc:o:t:v', ['--help', '--DEBUG', '--creds=', '--outfile=', '--token=', '--verbose'])
    for opt, a in optlist:
        if opt in ('-h', '--help'):
            usage()
        if opt in ('-D', '--DEBUG'):
            DEBUG = True
            VERBOSE = True
        if opt in ('-c', '--creds'):
            (user, password) = a.split(':')
        if opt in ('-o', '--outfile'):
            outfile = a
        if opt in ('-t', '--token'):
            token = a
        if opt in ('-v', '--verbose'):
            VERBOSE = True

    try:
        rubrik_host = args[0]
    except:
        usage()
    if DEBUG:
        pp = pprint.PrettyPrinter(indent=4)
    if not token and not user:
        user = python_input("User: ")
    if not token and not password:
        password = getpass.getpass("Password: ")

    if token:
        rubrik = rubrik_cdm.Connect(rubrik_host,api_token=token)
    else:
        rubrik = rubrik_cdm.Connect(rubrik_host, user, password)
    rubrik_config = rubrik.get('v1', '/cluster/me', timeout=timeout)
    rubrik_tz = rubrik_config['timezone']['timezone']
    local_zone = pytz.timezone(rubrik_tz)
    utz_zone = pytz.timezone('utc')
    vprint("Gathering Share Data...")
    hs_data = rubrik.get('internal', '/host/share', timeout=timeout)
    for hd in hs_data['data']:
        if hd['status'] == "REPLICATION_TARGET":
            continue
        host_inst = {'id': hd['id'], 'host': hd['hostname'], 'share': hd['exportPoint'], 'protocol': hd['shareType']}
        if 'vendorType' in hd:
            host_inst['vendor'] = hd['vendorType']
            if host_inst['vendor'] == "ISILON":
                try:
                    host_inst['array_scan'] = hd['hostShareParameters']['isIsilonChangelistEnabled']
                except Exception as e:
                    host_inst['array_scan'] = False
            elif host_inst['vendor'] == "NETAPP":
                try:
                    host_inst['array_scan'] = hd['hostShareParameters']['isNetAppSnapDiffEnabled']
                except:
                    host_inst['array_scan'] = False
            else:
                host_inst['array_scan'] = False
        else:
            host_inst['vendor'] = "Generic"
            host_inst['array_scan'] = False
        share_list[host_inst['id']] = host_inst
    dprint("SHARE_LIST:", 0)
    dprint(share_list, 1)
    vprint("Gathering Fileset and Event Data...")
    for share in share_list:
        fs_data = rubrik.get('v1', '/fileset?share_id=' + str(share), timeout=timeout)
        if fs_data['total'] == 0:
            continue
        for fs in fs_data['data']:
            if fs['configuredSlaDomainId'] == "UNPROTECTED":
                continue
            fs_inst = {'id': fs['id'], 'share_id': share_list[share]['id'], 'name': fs['templateName']}
            snap_info = rubrik.get('v1', '/fileset/' + str(fs_inst['id']), timeout=timeout)
            if snap_info['snapshotCount'] == 0:
                continue
            fs_inst['date'] = snap_info['snapshots'][-1]['date']
            bu_events = rubrik.get('v1', '/event/latest?limit=10&object_ids=' + str(share) + ',' + str(fs_inst['id']), timeout=timeout)
            for event in bu_events['data']:
                dprint("EV: ", 0)
                dprint(event['latestEvent'], 1)
                dprint("TYPE: " + str(event['latestEvent']['eventType']) + " // " + str(event['eventSeriesStatus']), 0)
                if event['latestEvent']['eventType'] != "Backup" or (event['latestEvent']['eventType'] == "Backup" and event['eventSeriesStatus'] != "Success"):
                    dprint("SKIPPING", 0)
                    continue
                dprint("FOUND GOOD BACKUP", 0)
                fs_inst['event_id'] = event['latestEvent']['eventSeriesId']
                break
            try:
                if fs_inst['event_id']:
                    fs_list.append(fs_inst)
            except:
                pass
    dprint("FS_LIST: ", 0)
    dprint(fs_list, 1)
    vprint("Creating Report...")
    if outfile:
        ofh = open(outfile, "w")
    oprint("Host:,Share:,Fileset:,Vendor:,Array Scan:,Protocol:,Time:,Duration:,Scan Rate:,Data Transferred:,Throughput:\n", ofh)
    for fs in fs_list:
        s_time = fs['date']
        s_time = s_time[:-5]
        s_time_dt = datetime.datetime.strptime(s_time, '%Y-%m-%dT%H:%M:%S')
        s_time_dt_s = pytz.utc.localize(s_time_dt).astimezone(local_zone)
        s_time_dt_s = str(s_time_dt_s)[:16]
        event_series = rubrik.get('v1', '/event_series/' + str(fs['event_id']))
        dur = event_series['duration'].split(' ')
        if dur[-1] == "ms":
            dur.pop()
            dur.pop()
        dur_s = " ".join(dur)
        if share_list[fs['share_id']]['array_scan']:
            aa_flag = "Y"
        else:
            aa_flag = "N"
        fps = get_scan_rate(event_series)
        oprint(share_list[fs['share_id']]['host'] + "," + share_list[fs['share_id']]['share'] + "," + fs['name'] + ",", ofh)
        oprint(share_list[fs['share_id']]['vendor'] + "," + aa_flag + "," + share_list[fs['share_id']]['protocol'] + ",", ofh)
        oprint(s_time_dt_s + "," + dur_s + "," + str(get_scan_rate(event_series)) + " f/s" + ",", ofh)
        oprint(byte_convert(event_series['dataTransferred']) + "," + byte_convert(event_series['throughput']) + "/s\n", ofh)