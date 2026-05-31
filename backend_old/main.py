import pandas as pd
from forgelab.server import start


pd.options.mode.copy_on_write = True


if __name__ == '__main__':
    start()
