import os
import logging

####################
# ENABLING LOGGING #
####################

logger = logging.getLogger(__name__)
if "LOG_LEVEL" in os.environ:
    logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL")))
else:
    logger.setLevel(getattr(logging, "INFO"))
LOG_LEVEL = logger.level
