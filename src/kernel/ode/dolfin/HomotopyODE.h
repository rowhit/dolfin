// Copyright (C) 2005 Johan Hoffman and Anders Logg.
// Licensed under the GNU GPL Version 2.

#ifndef __HOMOTOPY_ODE_H
#define __HOMOTOPY_ODE_H

#include <dolfin/constants.h>
#include <dolfin/ComplexODE.h>

namespace dolfin
{

  class Homotopy;

  /// This is the base class for complex homotopy ODEs. One ODE is
  /// generated by the class Homotopy for each homotopy path.
  
  class HomotopyODE : public ComplexODE
  {
  public:
  
    /// Current state, solving ODE or playing end game
    enum State { ode, endgame };

    /// Constructor
    HomotopyODE(Homotopy& homotopy, uint n);

    /// Destructor
    ~HomotopyODE();

    /// Return initial value for given component
    complex z0(unsigned int i);

    /// Evaluate right-hand side
    virtual void feval(const complex z[], real t, complex f[]);
    
    /// Compute product y = Mx for implicit system
    virtual void M(const complex x[], complex y[], const complex z[], real t);

    /// Compute product y = Jx for Jacobian J
    virtual void J(const complex x[], complex y[], const complex u[], real t);

    /// Update ODE, return false to stop (optional)
    virtual bool update(const complex z[], real t, bool end);

    /// Get state, solving ODE or playing end game
    State state();

  private:

    // The homotopy
    Homotopy& homotopy;

    // Size of system
    uint n;

    // Current state
    State _state;

  };

}

#endif
