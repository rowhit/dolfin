"""This module provides functionality for form assembly in Python,
corresponding to the C++ assembly and PDE classes.

The C++ assemble function (renamed to cpp_assemble) is wrapped with
an additional preprocessing step where code is generated using the
FFC JIT compiler.

The C++ PDE classes are reimplemented in Python since the C++ classes
rely on the dolfin::Form class which is not used on the Python side."""

__author__ = "Anders Logg (logg@simula.no)"
__date__ = "2007-08-15 -- 2008-01-01"
__copyright__ = "Copyright (C) 2007 Anders Logg"
__license__  = "GNU LGPL Version 2.1"

from ffc import *
from dolfin import *

# JIT assembler
def assemble(form, mesh, backend=None, return_dofmaps=False):
    "Assemble form over mesh and return tensor"
    
    # Compile form
    (compiled_form, module, form_data) = jit(form)

    # Extract coefficients
    coefficients = ArrayFunctionPtr()
    for c in form_data.coefficients:
        coefficients.push_back(c.f)

    # Create dummy arguments (not yet supported)
    cell_domains = MeshFunction("uint")
    exterior_facet_domains = MeshFunction("uint")
    interior_facet_domains = MeshFunction("uint")

    # Create dof maps
    dof_maps = DofMapSet(compiled_form, mesh)

    # Create tensor
    rank = compiled_form.rank()
    if rank == 0:
        tensor = Scalar()
    elif rank == 1:
        if backend:
            tensor = backend.createVector()
        else:
            tensor = Vector()
    elif rank == 2:
        if backend:
            tensor = backend.createMatrix()
        else:
            tensor = Matrix()
    else:
        raise RuntimeError, "Unable to assemble tensors of rank %d." % rank

    # Assemble compiled form
    cpp_assemble(tensor, compiled_form, mesh, coefficients, dof_maps,
                 cell_domains, exterior_facet_domains, interior_facet_domains, True)

    # Convert to float for scalars
    if rank == 0:
        tensor = tensor.getval()

    # Return value
    if return_dofmaps:
        return (tensor, dof_maps)
    else:
        return tensor

# Rename FFC Function
ffc_Function = Function

# Create new class inheriting from both FFC and DOLFIN Function
class Function(ffc_Function, cpp_Function):

    def __init__(self, element, *others):
        "Create Function"
        # Special case, Function(element, mesh, x), need to create simple form to get arguments
        if (isinstance(element, FiniteElement) or isinstance(element, MixedElement)) and \
               len(others) == 2 and isinstance(others[0], Mesh) and isinstance(others[1], Vector):
            mesh = others[0]
            x = others[1]
            # Create simplest possible form
            if element.value_dimension(0) > 1:
                form = TestFunction(element)[0]*dx
            else:
                form = TestFunction(element)*dx
            # Compile form and create dof map
            (compiled_form, module, form_data) = jit(form)
            self.dof_maps = DofMapSet(compiled_form, mesh)
            # Initialize FFC and DOLFIN Function
            ffc_Function.__init__(self, element)
            cpp_Function.__init__(self, mesh, x, self.dof_maps.sub(0), compiled_form, 0)
        # If we have an element, then give element to FFC and the rest to DOLFIN
        elif isinstance(element, FiniteElement) or isinstance(element, MixedElement):
            ffc_Function.__init__(self, element)
            cpp_Function.__init__(self, *others)
        # Otherwise give all to DOLFIN
        else:
            cpp_Function.__init__(self, *((element,) + others))

    def split(self):
        "Extract subfunctions"
        return tuple([Function(self.e0.sub_element(i), self.sub(i)) for i in range(self.numSubFunctions())])

# Create new class inheriting from both FFC and DOLFIN FacetNormal
# (FFC FacetNormal is a function that returns a FFC Function object)
class FacetNormal(ffc_Function, cpp_FacetNormal):

    def __init__(self, shape, mesh):
        "Create FacetNormal"

        element = VectorElement("Discontinuous Lagrange", shape, 0)
        ffc_Function.__init__(self, element)
        cpp_FacetNormal.__init__(self, mesh)

# Create new class inheriting from FFC MeshSize and DOLFIN MeshSize
# (FFC MeshSize is a function that returns a FFC Function object)
class MeshSize(ffc_Function, cpp_MeshSize):

    def __init__(self, shape, mesh):
        "Create MeshSize"

        element = FiniteElement("Discontinuous Lagrange", shape, 0)
        ffc_Function.__init__(self, element)
        cpp_MeshSize.__init__(self, mesh)

# Create new class inheriting from FFC MeshSize and DOLFIN AvgMeshSize
# (FFC MeshSize is a function that returns a FFC Function object)
class AvgMeshSize(ffc_Function, cpp_AvgMeshSize):

    def __init__(self, shape, mesh):
        "Create AvgMeshSize"

        element = FiniteElement("Discontinuous Lagrange", shape, 0)
        ffc_Function.__init__(self, element)
        cpp_AvgMeshSize.__init__(self, mesh)

# LinearPDE class
class LinearPDE:
    """A LinearPDE represents a (system of) linear partial differential
    equation(s) in variational form: Find u in V such that
    
        a(v, u) = L(v) for all v in V',

    where a is a bilinear form and L is a linear form."""

    def __init__(self, a, L, mesh, bcs=[]):
        "Create LinearPDE"

        self.a = a
        self.L = L
        self.mesh = mesh
        self.bcs = bcs
        self.x = Vector()
        self.dof_maps = DofMapSet()

        # Make sure we have a list
        if not isinstance(self.bcs, list):
            self.bcs = [self.bcs]

    def solve(self):
        "Solve PDE and return solution"

        begin("Solving linear PDE.");
        # Assemble linear system
        (A, self.dof_maps) = assemble(self.a, self.mesh, return_dofmaps=True)
        (b, dof_maps_L)    = assemble(self.L, self.mesh, return_dofmaps=True)

        # FIXME: Maybe there is a better solution?
        # Compile form, needed to create discrete function
        (compiled_form, module, form_data) = jit(self.a)

        # Apply boundary conditions
        for bc in self.bcs:
            cpp_DirichletBC.apply(bc, A, b, self.dof_maps.sub(1), compiled_form)

        #message("Matrix:")
        #A.disp()

        #message("Vector:")
        #b.disp()

        # Choose linear solver
        solver_type = get("PDE linear solver")
        if solver_type == "direct":
            message("Using direct solver.")
            solver = LUSolver()
            #solver.set("parent", self)
        elif solve_type == "iterative":
            message("Using iterative solver (GMRES).")
            solver = KrylovSolver(gmres)
            #solver.set("parent", self)
        else:
            error("Unknown solver type \"%s\"." % solver_type)

        # Solver linear system
        solver.solve(A, self.x, b)
        
        #message("Solution vector:")
        #self.x.disp()

        # Get trial element
        element = form_data.elements[1]
  
        # Create Function
        u = Function(element, self.mesh, self.x, self.dof_maps.sub(1), compiled_form)

        end()

        return u

# DirichletBC class (need to compile form before calling constructor)
class DirichletBC(cpp_DirichletBC):

    def __init__(self, *args):
        "Create Dirichlet boundary condition"
        cpp_DirichletBC.__init__(self, *args)

    def apply(self, A, b, form):
        "Apply boundary condition to linear system"
        
        # Compile form
        (compiled_form, module, form_data) = jit(form)        

        # Create dof maps
        dof_maps = DofMapSet(compiled_form, self.mesh())
        
        # Apply boundary condition
        cpp_DirichletBC.apply(self, A, b, dof_maps.sub(1), compiled_form)
