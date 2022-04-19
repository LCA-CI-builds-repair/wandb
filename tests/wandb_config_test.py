"""
config tests.
"""

import pytest
import yaml
from wandb import wandb_sdk
from wandb.errors import ConfigError


def get_callback(d):
    def callback_func(key=None, val=None, data=None):
        print("CONFIG", key, val, data)
        if data:
            d.update(data)
        if key:
            d[key] = val

    return callback_func


@pytest.fixture()
def consolidated():
    return {}


@pytest.fixture()
def callback(consolidated):
    return get_callback(consolidated)


@pytest.fixture()
def config(callback):
    s = wandb_sdk.Config()
    s._set_callback(callback)
    return s


def test_attrib_set(consolidated, config):
    config.this = 2
    assert dict(config) == dict(this=2)
    assert consolidated == dict(config)


def test_locked_set_attr(consolidated, config):
    config.update_locked(dict(this=2, that=4), "sweep")
    config.this = 8
    assert config.this == 2
    assert config.that == 4
    assert dict(config) == dict(this=2, that=4)
    assert consolidated == dict(config)


def test_locked_set_key(consolidated, config):
    config.update_locked(dict(this=2, that=4), "sweep")
    config["this"] = 8
    assert config["this"] == 2
    assert config["that"] == 4
    assert dict(config) == dict(this=2, that=4)
    assert consolidated == dict(config)


def test_update(consolidated, config):
    config.update(dict(this=8))
    assert dict(config) == dict(this=8)
    config.update(dict(that=4))
    assert dict(config) == dict(this=8, that=4)
    assert consolidated == dict(config)


def test_setdefaults(consolidated, config):
    config.update(dict(this=8))
    assert dict(config) == dict(this=8)
    config.setdefaults(dict(extra=2, another=4))
    assert dict(config) == dict(this=8, extra=2, another=4)
    assert consolidated == dict(config)


def test_setdefaults_existing(consolidated, config):
    config.update(dict(this=8))
    assert dict(config) == dict(this=8)
    config.setdefaults(dict(extra=2, this=4))
    assert dict(config) == dict(this=8, extra=2)
    assert consolidated == dict(config)


def test_locked_update(consolidated, config):
    config.update_locked(dict(this=2, that=4), "sweep")
    config.update(dict(this=8))
    assert dict(config) == dict(this=2, that=4)
    assert consolidated == dict(config)


def test_locked_no_sideeffect(consolidated, config):
    config.update_locked(dict(this=2, that=4), "sweep")
    update_arg = dict(this=8)
    config.update(update_arg)
    assert update_arg == dict(this=8)
    assert dict(config) == dict(this=2, that=4)
    assert consolidated == dict(config)


def test_load_config_default(runner):
    test_path = "config-defaults.yaml"
    yaml_dict = {"epochs": {"value": 32}, "size_batch": {"value": 32}}
    with runner.isolated_filesystem():
        with open(test_path, "w") as f:
            yaml.dump(yaml_dict, f, default_flow_style=False)
        config = wandb_sdk.Config()
        assert dict(config) == dict(epochs=32, size_batch=32)


def test_load_empty_config_default(runner, capsys):
    test_path = "config-defaults.yaml"
    with runner.isolated_filesystem():
        with open(test_path, "w") as f:
            pass
        _ = wandb_sdk.Config()
        err_log = capsys.readouterr().err
        warn_msg = "wandb: WARNING Found an empty default config file (config-defaults.yaml). Proceeding with no defaults."
        print(err_log)
        assert warn_msg in err_log


def test_nested_config_helpers():

    invalid_nested_config = {"foo": {1: 1}}
    with pytest.raises(ConfigError):
        _ = wandb_sdk.helper.unnest_config(invalid_nested_config)

    invalid_nested_config = {1: {"foo": 1}}
    with pytest.raises(ConfigError):
        _ = wandb_sdk.helper.unnest_config(invalid_nested_config)

    invalid_unnested_config = {1: "foo"}
    with pytest.raises(ConfigError):
        _ = wandb_sdk.helper.nest_config(invalid_unnested_config)

    invalid_unnested_config = {"foo": 1, "foo.bar": {"baz": 2}}
    with pytest.raises(ConfigError):
        _ = wandb_sdk.helper.nest_config(invalid_unnested_config)

    valid_nested_config = {"foo": {"bar": 1}}
    unnested_config = wandb_sdk.helper.unnest_config(valid_nested_config)
    renested_config = wandb_sdk.helper.nest_config(unnested_config)
    assert valid_nested_config == renested_config

    valid_nested_config = {"foo": {"bar": {"baz": 1, "boz": 2}}}
    unnested_config = wandb_sdk.helper.unnest_config(valid_nested_config)
    renested_config = wandb_sdk.helper.nest_config(unnested_config)
    assert valid_nested_config == renested_config
