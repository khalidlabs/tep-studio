from __future__ import annotations

import numpy as np

from tep_studio import TennesseeEastmanProcess


def main() -> None:
    sim = TennesseeEastmanProcess()
    obs, info = sim.reset(seed=1431655765)
    action = np.array([63.53, 53.98, 24.644, 61.302, 22.21, 40.064, 38.1, 46.534, 47.446, 38.0, 18.114, 50.0])
    print("initial reactor pressure:", obs[6])
    print("initial status:", info["shutdown_status"])

    while sim.time < 5.0:
        result = sim.advance(action, control_interval=0.01)
        if result.shutdown_status["terminated"]:
            print("terminated at h:", result.time)
            print(result.shutdown_status)
            break
    else:
        print("completed horizon without shutdown")


if __name__ == "__main__":
    main()
