import code
import numpy as np

from .hw import HW

def console():
    hw = HW()

    local_dict = {
        "hw": hw,
        "np": np,
    }

    code.interact(banner="Hardware available through `hw`.",
        local=local_dict)

if __name__ == "__main__":
    console()
