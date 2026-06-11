#ifndef PARTICLE_RECORDER_HH
#define PARTICLE_RECORDER_HH

#include "ParticleRecord.hh"
#include "CsvWriter.hh"

namespace janus
{

class ParticleRecorder
{
public:

    ParticleRecorder();

    void Record(const ParticleRecord& record);

private:

    CsvWriter fWriter;
};

}

#endif