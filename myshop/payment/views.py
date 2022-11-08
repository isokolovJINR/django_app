from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from orders.models import Order
from .tasks import payment_completed
# Create your views here.


def payment_process(request):
    order_id = request.session.get('order_id')
    order = get_object_or_404(Order, id=order_id)
    total_cost = order.get_total_cost()
    if request.method == 'POST':
        payment_completed.delay(order.id)
        return redirect('payment:done')
    else:
        return render(request,
                      'payment/process.html',
                      {'order': order,
                       'client_token': 'ssssss-asd-asd'})

    
def payment_done(request):
    return render(request, 'payment/done.html')