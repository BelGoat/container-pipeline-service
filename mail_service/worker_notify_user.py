#!/usr/bin/env python

import beanstalkc
import json
import subprocess
import re
import time
import smtplib

bs = beanstalkc.Connection(host="172.17.0.1")
bs.watch("notify_user")


def send_mail(notify_email, subject, msg, logs):
    if(logs is not None):
        failed_msg_command = "/mail_service/send_failed_mail.sh"
        logfile = open("/tmp/build_log.log","w")
        logfile.write(logs)
        logfile.close()
        subprocess.call(
            [failed_msg_command,subject,notify_email,msg,"/tmp/build_log.log"])
    else:
        success_msg_command = "/mail_service/send_success_mail.sh"
        subprocess.call([success_msg_command,subject,notify_email,msg])
#    SERVER = "localhost"
#    FROM = "container-build-report@centos.org"
#    TO = [notify_email] # must be a list
#    SUBJECT = subject
#    TEXT = msg+"\n"+logs

    # Prepare actual message

#    message = """\
#    From: %s
#    To: %s
#    Subject: %s

#    %s
#    """ % (FROM, ", ".join(TO), SUBJECT, TEXT)

    # Send the mail
#    server = smtplib.SMTP(SERVER)
#    server.sendmail(FROM, TO, message)
#   server.quit()

while True:
    print "Listening to notify_user tube"

    job = bs.reserve()
    jobid = job.jid
    job_details = json.loads(job.body)

    print "==> Retrieving message details"
    notify_email = job_details['notify_email']
    subject = job_details['subject']

    if 'msg' not in job_details :
        msg = None
    else:
        msg = job_details['msg']

    if 'logs' not in job_details :
        logs = None
    else:
        logs = job_details['logs']

    print "==> Sending email to user"
    send_mail(notify_email, subject, msg, logs)
    job.delete()
