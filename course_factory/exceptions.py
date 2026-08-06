class CourseFactoryError(Exception): pass
class AgentExecutionError(CourseFactoryError): pass
class InvalidStateTransitionError(CourseFactoryError): pass
class MissingCapabilityError(CourseFactoryError): pass
class RetryLimitExceededError(CourseFactoryError): pass
