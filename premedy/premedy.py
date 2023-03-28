import sys

from premedy.premedy_finding import PremedyFinding
from glob import glob
from pydoc import locate
import logging
from premedy import config

logger = logging.getLogger(__name__)
logger.setLevel(config.LOG_LEVEL)


class Premedy:
    def __init__(self, app, topic, project, path, use_subscription=True):
        self.app = app
        self.topic = topic
        self.project = project
        self.use_subscription = use_subscription
        self.remediation_classes = []
        self.path = path
        self.load_remediation_classes()
        self.consume = self.app.topic(
            topic=self.topic,
            project=self.project,
            use_subscription=self.use_subscription,
        )(self.consume)

    def consume(self, message):
        premedy_finding = PremedyFinding(message)
        premedy_finding.save_in_gcs_bucket()
        self.remediate(premedy_finding)
        return {}

    def remediate(self, premedy_finding: PremedyFinding):
        for remediation in self.remediation_classes:
            instance = remediation(premedy_finding=premedy_finding)
            self.app.log.info(f" Check Remediation Class {instance.__class__}")
            if instance.should_take_action():
                try:
                    self.app.log.info(
                        f" Take Action Remediation Class {instance.__class__}"
                    )
                    response = instance.remediate()
                    self.app.log.info(
                        f" Action Response Remediation Class {instance.__class__}: {response}"
                    )
                except:
                    self.app.log.error(f" Could not remediate: {instance.__class__}")

    def load_remediation_classes(self):
        sys.path.append(self.path)
        remediation_classes = []
        for file in glob(f"{self.path}/*.py"):
            logger.debug(f"loading: {file}")
            with open(file, "r") as f:
                line = ""
                while "class" not in line and "(RemediationBase)" not in line:
                    line = f.readline()
            class_name = (
                line.strip()
                .replace("(RemediationBase):", "")
                .replace("class ", "")
                .strip()
            )
            module_name = (
                file.replace("./", "")
                .replace(".py", "")
                .replace("/", ".")
                .split(".")[-1]
            )
            remediation_class = locate(f"{module_name}.{class_name}")
            if not remediation_class:
                logger.error(f"failed to load {file}")
                continue

            remediation_classes.append(remediation_class)
            logger.debug(f"loaded: class {class_name} from {file}")

        self.remediation_classes = remediation_classes
