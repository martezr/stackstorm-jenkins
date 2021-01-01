from lib import action
from time import sleep
from jenkins import NotFoundException, JenkinsException


class BuildProject(action.JenkinsBaseAction):
    def run(self, project, build_max_wait, build_wait_interval, queue_max_wait, queue_wait_interval, parameters=None, config_override=None):
        if config_override is not None:
            self.config_override(config_override)
        (status, queue_id) = self.kick_off_job(project, parameters)
        if status == 1:
            # try again without parameters
            (status, queue_id) = self.kick_off_job(project, {})
            if status > 0:
                # give up
                return False, queue_id
        elif status == 2:
            # queue_id will contain error
            return False, queue_id

        # wait for job to queue
        attempt = 0
        max_attempts = int(queue_max_wait / queue_wait_interval)
        run_build_result = False
        queue_item = None
        while attempt <= max_attempts and not run_build_result:
            queue_item = self.jenkins.get_queue_item(queue_id)
            if 'executable' in queue_item:
                run_build_result = True
                break
            else:
                attempt += 1
                sleep(queue_wait_interval)

        # wait for job to build
        attempt = 0
        max_attempts = int(build_max_wait / build_wait_interval)
        job_completed = False
        while attempt <= max_attempts and job_completed == False:
            build_status = self.jenkins.get_build_info(project, queue_item['executable']['number'], depth='1')
            if build_status['building'] == False:
                job_completed = True
                break
            else:
                attempt += 1
                sleep(build_wait_interval)

        if build_status['result'] == "SUCCESS":
            return True, build_status
        else:
            return False, build_status

    def kick_off_job(self, prj, prm):
        try:
            queue_id = self.jenkins.build_job(prj, prm)
        except NotFoundException:
            # terminal error
            return 2, {'error': 'Project {0} not found.'.format(prj)}
        except JenkinsException as e:
            msg = e.message
            msg = msg.encode('ascii', 'ignore')
            if 'doBuildWithParameters' in msg:
                # most likely build is not parameterized but we sent parameters,
                # return non-terminal status
                return 1, {}
            else:
                # most likely something else and very bad happened, return terminal status
                return 2, {'error': 'General error: {0}'.format(msg)}
        else:
            return 0, queue_id