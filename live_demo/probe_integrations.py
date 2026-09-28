"""Print the live provider registry without making provider inference calls."""
import json
from demo.live_demo import ProviderRegistry

if __name__ == "__main__":
    print(json.dumps({"providers": [r.public() for r in ProviderRegistry().records()]}, indent=2, sort_keys=True))
