#!/usr/bin/env python
import hashlib
import json
import logging
import os

from container_pipeline.lib import settings
from container_pipeline.lib.log import load_logger
from container_pipeline.lib.openshift import Openshift, OpenshiftError
from container_pipeline.utils import Build, get_job_name, get_project_name
from container_pipeline.workers.base import BaseWorker


class TestWorker(BaseWorker):
    """
    Test Worker.

    Runs the user defined tests on a built container in the pipeline.
    """

    NAME = 'Test worker'

    def __init__(self, logger=None, sub=None, pub=None):
        super(TestWorker, self).__init__(logger, sub, pub)
        self.openshift = Openshift(logger=self.logger)

    def run_test(self, job):
        """Run Openshift test build for job, which runs the user
        defined tests."""
        namespace = get_job_name(job)
        project = hashlib.sha224(namespace).hexdigest()

        try:
            self.openshift.login()

            # TODO: This needs to be addressed after addressing Issue #276
            build_id = self.openshift.build(project, 'test')
            if not build_id:
                return False
        except OpenshiftError as e:
            self.logger.error(e)
            return False

        Build(namespace).start()
        test_status = self.openshift.wait_for_build_status(
            project, build_id, 'Complete', status_index=2)
        logs = self.openshift.get_build_logs(project, build_id)
        test_logs_file = os.path.join(job['logs_dir'], 'test_logs.txt')
        self.export_logs(logs, test_logs_file)
        return test_status

    def handle_test_success(self, job):
        """Handle test success for job."""
        job['action'] = "start_scan"
        # TODO: Below five variables are to be removed and they should in job
        # from jenkins
        job['output_image'] = "{}/{}/{}:{}".format(settings.REGISTRY_ENDPOINT[0],
                                                   job['appid'], job['jobid'], job['test_tag'])
        job['image_name'] = "{}/{}:{}".format(job['appid'],
                                              job['jobid'], job['desired_tag'])
        job['build_status'] = True
        job['beanstalk_server'] = settings.BEANSTALKD_HOST
        job['namespace'] = job['project_name']

        self.queue.put(json.dumps(job), 'master_tube')
        self.logger.debug("Test is successful going for next job")

    def handle_test_failure(self, job):
        """Handle test failure for job"""
        job.pop('action', None)
        job['action'] = "test_failure"
        self.queue.put(json.dumps(job), 'master_tube')
        self.logger.warning(
            "Test is not successful putting it to failed build tube")
        data = {
            'action': 'notify_user',
            'namespace': get_job_name(job),
            'build_status': False,
            'notify_email': job['notify_email'],
            'test_logs_file': os.path.join(
                job['logs_dir'], 'test_logs.txt'),
            'project_name': get_project_name(job),
            'job_name': job['jobid'],
            'test_tag': job['test_tag']}
        self.logger.debug('Notify test failure: {}'.format(data))
        self.notify(data)

    def handle_job(self, job):
        """This runs the test worker"""
        success = self.run_test(job)

        if success:
            self.handle_test_success(job)
        else:
            self.handle_test_failure(job)


if __name__ == '__main__':
    load_logger()
    logger = logging.getLogger('test-worker')
    worker = TestWorker(logger, sub='start_test', pub='test_failed')
    worker.run()
