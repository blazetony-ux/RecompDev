#pragma once
#include "sms.hpp"
#include "../runtime.hpp"
namespace recomp::hw::sms {
class Machine final: public VideoSource,public AudioSource,public InputTarget {
 std::shared_ptr<Vdp> vdp_=std::make_shared<Vdp>();
 std::shared_ptr<Psg> psg_=std::make_shared<Psg>();
 std::shared_ptr<Controller> controller_=std::make_shared<Controller>();
 public:
 void connect(Runtime& r){r.bus().attach(vdp_);r.bus().attach(psg_);r.bus().attach(controller_);
  r.video(*this,std::make_shared<HeadlessFrames>());r.audio(*this,std::make_shared<HeadlessAudio>());r.input(*this);}
 Frame render()const override{return vdp_->render();}
 std::int16_t sample(u64 c)override{return psg_->sample(c);}
 void set_input(InputState s)override{controller_->set_input(s);}
 std::shared_ptr<Vdp> vdp()const{return vdp_;}
 std::shared_ptr<Psg> psg()const{return psg_;}
 std::shared_ptr<Controller> controller()const{return controller_;}
};
}
