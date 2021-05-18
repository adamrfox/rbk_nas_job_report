# rbk_nas_job_report
A project to give a detailed report on NAS jobs on Rubrik

This script does a detailed report for NAS backup jobs that do not currently exist in the Rubrik user interface.  It leverages the power of the Rubrik CDM API to pull the information about the job.  It generates a CSV file which can then be pulled into many tools to generate a presentable report.

This is work in progress.  Currently the code will find all of the NAS filesets on the Rubrik but will exclude any of the following:

1. Any fileset that is not currnetly assigned to an SLA for protection.
2. Any replicated filesets (these would be tracked on the source Rubrik)
3. Any fileset that has not had a recent successful backup.  I look at the last 10 tasks currently.
4. It only reports on the latest successful backup job for each fileset.

The following fileset information is being pulled.  This could change per customer needs.

NAS Host Name
Share Name
Fileset name
NAS Vendor
Array Scanning?  (SnapDiff/ChangeList)
Protocol
Backup Start time
Backup Duration
Scan Rate
Data Transferred
Data Throughput

<PRE>
Usage: rbk_nas_job_report.py [-hDv] [-o output_file] [-c creds] [-t token] rubrik
-h | --help : Prints this message
-D | --DEBUG : Prints a lot of debug information for the developer
-v | --verbose : Prints progress messages while the script runs
-o | --outout= : Specify an output file for the report (csv format)
-c | --creds= : Specify the creds on the CLI. By default the user is prompted
-t | --token= : Specify an API token instead of credentials
rubrik : Name or IP of a Rubrik node
</PRE>

The script is written in Python.  It should work with either Python 2 or 3.  It does require the Rubrik SDK library which can be pip'ed in with the name 'rubrik_cdm'.  The rest of the libraries should be standard.
