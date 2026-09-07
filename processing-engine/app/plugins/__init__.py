# Import all sub-packages to trigger plugin registration.
# The order matters: registry must be importable before sub-packages run.
import app.plugins.dedup  # noqa: F401
import app.plugins.ingestors  # noqa: F401
import app.plugins.llm  # noqa: F401
import app.plugins.sinks  # noqa: F401
import app.plugins.validators  # noqa: F401
