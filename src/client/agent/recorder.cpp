/*
Minetest
Copyright (C) 2010-2013 celeron55, Perttu Ahola <celeron55@gmail.com>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation; either version 2.1 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
*/

#include "recorder.h"

void Recorder::setAction(pb_objects::Action & action) {
    actionToSend = action;
}

void Recorder::setImage(pb_objects::Image & img) {
    imgToSend = img;
}

void Recorder::setReward(float & reward) {
    rewardToSend = reward;
}

void Recorder::setInfo(std::string & info) {
	infoToSend = info;
}

void Recorder::setTerminal(bool & terminal) {
    terminalToSend = terminal;
}

// TODO: move OutputObservation creation outside the function
void Recorder::sendObservation() {
    pb_objects::Observation obsToSend;
    obsToSend.set_reward(rewardToSend);
    obsToSend.set_info(infoToSend);
    obsToSend.set_terminal(terminalToSend);
    obsToSend.set_allocated_image(&imgToSend);
    obsToSend.set_allocated_action(&actionToSend);
    std::string msg = obsToSend.SerializeAsString();
    obsToSend.release_image();
    obsToSend.release_action();
    sender->send(msg);
}
