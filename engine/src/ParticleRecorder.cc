#include "ParticleRecorder.hh"

namespace janus
{

ParticleRecorder::ParticleRecorder()
{}

void ParticleRecorder::Record(
    const ParticleRecord& record
)
{
    fWriter.Write(record);
}

}