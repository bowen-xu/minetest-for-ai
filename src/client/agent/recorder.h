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

#pragma once

#include "client/client.h"
#include "client/proto/objects.pb.h"
#include <zmqpp/zmqpp.hpp>
#include <string>

class Recorder
{
public:
	Recorder(){};
	void setAction(pb_objects::Action & action);
	void setImage(pb_objects::Image & img);
	void setReward(float & reward);
	void setInfo(std::string & info);
	void setTerminal(bool & terminal);
    void sendObservation();

    zmqpp::socket *sender = nullptr;

private:
    zmqpp::context context;
	pb_objects::Action actionToSend;
	pb_objects::Image imgToSend;
	float rewardToSend;
	bool terminalToSend;
	std::string infoToSend;
};
