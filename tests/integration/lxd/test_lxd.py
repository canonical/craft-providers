from craft_providers.lxd import LXD


def test_setup():
    # Test LXD setup. Of course we cannot forcibly purge LXD from host for
    # a clean test, just work with whatever environment is provided.
    lxd = LXD()
    lxd.setup()
