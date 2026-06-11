#ifndef CSV_WRITER_HH
#define CSV_WRITER_HH

#include "ParticleRecord.hh"

#include <fstream>

namespace janus
{

class CsvWriter
{
public:

    CsvWriter();
    ~CsvWriter();

    void Write(const ParticleRecord& record);

private:

    std::ofstream fOutFile;
};

}

#endif
