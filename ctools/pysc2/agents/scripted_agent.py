# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Scripted agents."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy

from ctools.pysc2.agents import base_agent
from ctools.pysc2.lib import actions
from ctools.pysc2.lib import features

_PLAYER_SELF = features.PlayerRelative.SELF
_PLAYER_NEUTRAL = features.PlayerRelative.NEUTRAL  # beacon/minerals
_PLAYER_ENEMY = features.PlayerRelative.ENEMY

FUNCTIONS = actions.FUNCTIONS
RAW_FUNCTIONS = actions.RAW_FUNCTIONS


def _xy_locs(mask):
  """Mask should be a set of bools from comparison with a feature layer."""
  y, x = mask.nonzero()
  return list(zip(x, y))


class MoveToBeacon(base_agent.BaseAgent):
  """An agent specifically for solving the MoveToBeacon map."""

  def step(self, obs):
    super(MoveToBeacon, self).step(obs)
    if FUNCTIONS.Move_screen.id in obs.observation.available_actions:
      player_relative = obs.observation.feature_screen.player_relative
      beacon = _xy_locs(player_relative == _PLAYER_NEUTRAL)
      if not beacon:
        return FUNCTIONS.no_op()
      beacon_center = numpy.mean(beacon, axis=0).round()
      return FUNCTIONS.Move_screen("now", beacon_center)
    else:
      return FUNCTIONS.select_army("select")


class CollectMineralShards(base_agent.BaseAgent):
  """An agent specifically for solving the CollectMineralShards map."""

  def step(self, obs):
    super(CollectMineralShards, self).step(obs)
    if FUNCTIONS.Move_screen.id in obs.observation.available_actions:
      player_relative = obs.observation.feature_screen.player_relative
      minerals = _xy_locs(player_relative == _PLAYER_NEUTRAL)
      if not minerals:
        return FUNCTIONS.no_op()
      marines = _xy_locs(player_relative == _PLAYER_SELF)
      marine_xy = numpy.mean(marines, axis=0).round()  # Average location.
      distances = numpy.linalg.norm(numpy.array(minerals) - marine_xy, axis=1)
      closest_mineral_xy = minerals[numpy.argmin(distances)]
      return FUNCTIONS.Move_screen("now", closest_mineral_xy)
    else:
      return FUNCTIONS.select_army("select")


class CollectMineralShardsFeatureUnits(base_agent.BaseAgent):
  """An agent for solving the CollectMineralShards map with feature units.

  Controls the two marines independently:
  - select marine
  - move to nearest mineral shard that wasn't the previous target
  - swap marine and repeat
  """

  def setup(self, obs_spec, action_spec):
    super(CollectMineralShardsFeatureUnits, self).setup(obs_spec, action_spec)
    if "feature_units" not in obs_spec:
      raise Exception("This agent requires the feature_units observation.")

  def reset(self):
    super(CollectMineralShardsFeatureUnits, self).reset()
    self._marine_selected = False
    self._previous_mineral_xy = [-1, -1]

  def step(self, obs):
    super(CollectMineralShardsFeatureUnits, self).step(obs)
    marines = [unit for unit in obs.observation.feature_units
               if unit.alliance == _PLAYER_SELF]
    if not marines:
      return FUNCTIONS.no_op()
    marine_unit = next((m for m in marines
                        if m.is_selected == self._marine_selected), marines[0])
    marine_xy = [marine_unit.x, marine_unit.y]

    if not marine_unit.is_selected:
      # Nothing selected or the wrong marine is selected.
      self._marine_selected = True
      return FUNCTIONS.select_point("select", marine_xy)

    if FUNCTIONS.Move_screen.id in obs.observation.available_actions:
      # Find and move to the nearest mineral.
      minerals = [[unit.x, unit.y] for unit in obs.observation.feature_units
                  if unit.alliance == _PLAYER_NEUTRAL]

      if self._previous_mineral_xy in minerals:
        # Don't go for the same mineral shard as other marine.
        minerals.remove(self._previous_mineral_xy)

      if minerals:
        # Find the closest.
        distances = numpy.linalg.norm(
            numpy.array(minerals) - numpy.array(marine_xy), axis=1)
        closest_mineral_xy = minerals[numpy.argmin(distances)]

        # Swap to the other marine.
        self._marine_selected = False
        self._previous_mineral_xy = closest_mineral_xy
        return FUNCTIONS.Move_screen("now", closest_mineral_xy)

    return FUNCTIONS.no_op()


class CollectMineralShardsRaw(base_agent.BaseAgent):
  """An agent for solving CollectMineralShards with raw units and actions.

  Controls the two marines independently:
  - move to nearest mineral shard that wasn't the previous target
  - swap marine and repeat
  """

  def setup(self, obs_spec, action_spec):
    super(CollectMineralShardsRaw, self).setup(obs_spec, action_spec)
    if "raw_units" not in obs_spec:
      raise Exception("This agent requires the raw_units observation.")

  def reset(self):
    super(CollectMineralShardsRaw, self).reset()
    self._last_marine = None
    self._previous_mineral_xy = [-1, -1]

  def step(self, obs):
    super(CollectMineralShardsRaw, self).step(obs)
    marines = [unit for unit in obs.observation.raw_units
               if unit.alliance == _PLAYER_SELF]
    if not marines:
      return RAW_FUNCTIONS.no_op()
    marine_unit = next((m for m in marines if m.tag != self._last_marine))
    marine_xy = [marine_unit.x, marine_unit.y]

    minerals = [[unit.x, unit.y] for unit in obs.observation.raw_units
                if unit.alliance == _PLAYER_NEUTRAL]

    if self._previous_mineral_xy in minerals:
      # Don't go for the same mineral shard as other marine.
      minerals.remove(self._previous_mineral_xy)

    if minerals:
      # Find the closest.
      distances = numpy.linalg.norm(
          numpy.array(minerals) - numpy.array(marine_xy), axis=1)
      closest_mineral_xy = minerals[numpy.argmin(distances)]

      self._last_marine = marine_unit.tag
      self._previous_mineral_xy = closest_mineral_xy
      return RAW_FUNCTIONS.Move_pt("now", marine_unit.tag, closest_mineral_xy)

    return RAW_FUNCTIONS.no_op()


class DefeatRoaches(base_agent.BaseAgent):
  """An agent specifically for solving the DefeatRoaches map."""

  def step(self, obs):
    super(DefeatRoaches, self).step(obs)
    if FUNCTIONS.Attack_screen.id in obs.observation.available_actions:
      player_relative = obs.observation.feature_screen.player_relative
      roaches = _xy_locs(player_relative == _PLAYER_ENEMY)
      if not roaches:
        return FUNCTIONS.no_op()

      # Find the roach with max y coord.
      target = roaches[numpy.argmax(numpy.array(roaches)[:, 1])]
      return FUNCTIONS.Attack_screen("now", target)

    if FUNCTIONS.select_army.id in obs.observation.available_actions:
      return FUNCTIONS.select_army("select")

    return FUNCTIONS.no_op()


class DefeatRoachesRaw(base_agent.BaseAgent):
  """An agent specifically for solving DefeatRoaches using raw actions."""

  def setup(self, obs_spec, action_spec):
    super(DefeatRoachesRaw, self).setup(obs_spec, action_spec)
    if "raw_units" not in obs_spec:
      raise Exception("This agent requires the raw_units observation.")

  def step(self, obs):
    super(DefeatRoachesRaw, self).step(obs)
    marines = [unit.tag for unit in obs.observation.raw_units
               if unit.alliance == _PLAYER_SELF]
    roaches = [unit for unit in obs.observation.raw_units
               if unit.alliance == _PLAYER_ENEMY]

    if marines and roaches:
      # Find the roach with max y coord.
      target = sorted(roaches, key=lambda r: r.y)[0].tag
      return RAW_FUNCTIONS.Attack_unit("now", marines, target)

    return FUNCTIONS.no_op()
