// REQ-015: one function defined in both branches of a preprocessor #if.
#if !defined(EDGE_STUB)

#include <cstddef>

struct edge_pipeline {
    int n;
};

edge_pipeline * edge_pipeline_init(const int * devices, size_t n_devices) {
    edge_pipeline * p = new edge_pipeline;
    p->n = (int) n_devices;
    if (devices == nullptr) {
        return nullptr;
    }
    return p;
}

#else // defined(EDGE_STUB)
// The stub branch: no pipeline at all, callers treat nullptr as "unavailable".

edge_pipeline * edge_pipeline_init(const int *, size_t) {
    return nullptr;
}

#endif // !defined(EDGE_STUB)
