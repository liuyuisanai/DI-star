import os
import sys
from abc import ABC, abstractmethod, abstractproperty
from collections import namedtuple
from typing import Any
import uuid

from ctools.utils import build_logger_naive, EasyTimer, get_task_uid, VariableRecord, import_module
from .comm.actor_comm_helper import ActorCommHelper


class BaseActor(ABC):

    def __init__(self, cfg: dict) -> None:
        self._cfg = cfg
        self._init()
        if self._cfg.actor.communication.type == 'single_machine':
            self._logger.info('[WARNING]: use default single machine communication strategy')
            # TODO single machine actor
            raise NotImplementedError
        else:
            comm_cfg = self._cfg.actor.communication
            ActorCommHelper.enable_comm_helper(self, comm_cfg)

    def _init(self) -> None:
        self._actor_uid = str(uuid.uuid1())
        self._setup_logger()
        self._end_flag = False
        self._setup_timer()

    def _setup_timer(self):
        self._timer = EasyTimer()

        def agent_wrapper(fn):

            def wrapper(*args, **kwargs):
                with self._timer:
                    ret = fn(*args, **kwargs)
                self._variable_record.update_var({'agent_time': self._timer.value})
                return ret

            return wrapper

        def env_wrapper(fn):

            def wrapper(*args, **kwargs):
                with self._timer:
                    ret = fn(*args, **kwargs)
                size = sys.getsizeof(ret) / (1024 * 1024)  # MB
                self._variable_record.update_var(
                    {
                        'env_time': self._timer.value,
                        'timestep_size': size,
                        'norm_env_time': self._timer.value / size
                    }
                )
                return ret

            return wrapper

        self._agent_inference = agent_wrapper(self._agent_inference)
        self._env_step = env_wrapper(self._env_step)

    def _check(self) -> None:
        assert hasattr(self, 'init_service')
        assert hasattr(self, 'close_service')
        assert hasattr(self, 'get_job')
        assert hasattr(self, 'get_agent_update_info')
        assert hasattr(self, 'send_traj_metadata')
        assert hasattr(self, 'send_traj_stepdata')
        assert hasattr(self, 'send_result')

    def _init_with_job(self, job: dict) -> None:
        # update iter_count and varibale_record for each job
        self._iter_count = 0
        self._variable_record = VariableRecord(self._cfg.actor.print_freq)
        self._variable_record.register_var('agent_time')
        self._variable_record.register_var('env_time')
        self._variable_record.register_var('timestep_size')
        self._variable_record.register_var('norm_env_time')
        self._logger.info("ACTOR({}): JOB INFO:\n{}".format(self._actor_uid, job))

        # other parts need to be implemented by subclass

    def _setup_logger(self) -> None:
        path = os.path.join(self._cfg.common.save_path, 'log')
        name = 'actor.{}.log'.format(self._actor_uid)
        self._logger, self._variable_record = build_logger_naive(path, name)

    def run(self) -> None:
        self.init_service()
        job = self.get_job()
        self._init_with_job(job)
        while not self._end_flag:
            while True:
                obs = self._env_manager.next_obs
                action = self._agent_inference(obs)
                timestep = self._env_step(action)
                self._process_timestep(timestep)
                self._iter_after_hook()
                if self._env_manager.done:
                    break
            self.reset()

    def close(self) -> None:
        self.close_service()
        self._end_flag = True

    def _iter_after_hook(self):
        # print info
        if self._iter_count % self._cfg.actor.print_freq == 0:
            self._logger.info(
                'ACTOR({}):\n{}TimeStep{}{} {}'.format(
                    self._actor_uid, '=' * 35, self._iter_count, '=' * 35, self._variable_record.get_vars_text()
                )
            )
        self._iter_count += 1

    @abstractmethod
    def __repr__(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def _agent_inference(self, obs: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def _env_step(self, action: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def _process_timestep(self, timestep: namedtuple) -> None:
        raise NotImplementedError

    def _pack_trajectory(self) -> None:
        raise NotImplementedError

    def _update_agent(self) -> None:
        raise NotImplementedError


actor_mapping = {}


def register_actor(name: str, actor: BaseActor) -> None:
    assert isinstance(name, str)
    assert issubclass(actor, BaseActor)
    actor_mapping[name] = actor


def create_actor(cfg: dict) -> BaseActor:
    import_module(cfg.actor.import_names)
    if cfg.actor.actor_type not in actor_mapping.keys():
        raise KeyError("not support actor type: {}".format(cfg.actor.actor_type))
    else:
        return actor_mapping[cfg.actor.actor_type](cfg)
